#!/usr/bin/env python3
"""Why the 68 shared handlers of Section 5.3 are not recovered at the link layer (Section 5.9,
Supplementary S6). Added 2026-11-11 after the review of manuscript v3.5: the text had called
all 68 "inter-module registrations" without a per-name check.

Input: the 68 names (wl_ext.json: ext_link_unrecovered ∪ defined_link_unrecovered), the
link-layer files of allfiles.txt (linked modules, builtin objects, replacement units of modules
that failed to link) and llvm-dis. For every name and every link-layer file: whether the file
defines the function, how many direct calls it contains, and the categories of every other use
of the symbol (at_only.cat: global initializer, store, call argument, select/phi/ret, ptrtoint,
icmp, export artefacts). "Address taken" = any use outside the export artefacts
(__UNIQUE_ID___addressable, __ksymtab, llvm.used), icmp and the callee position of a direct
call, i.e. the same reading as Section 3.7 / at_only.py.

Classes (one per name):
  inter_module      address taken in a file of another kernel module (or the builtin aggregate)
                    than the one defining the function: the registration is invisible from the
                    defining module = inter-module registration
  unlinked_module   address taken in another unit of the same module, but that module is one of
                    the 12 whose llvm-link failed, so the link layer analysed its units one by
                    one (replacement units of allfiles.txt) and the registration stayed in
                    another unit
  own_module_only   address taken only in files that define it (unexpected: link FPEA should
                    see it; listed for inspection)
  direct_call_only  no address-taken use in any link-layer file: the whitelist matched the
                    name pattern of a helper that is only called directly
  not_defined       defined in no link-layer file

Files are named by the linked module (drivers_x_y.bc) or, for replacement units, by the unit
path relative to the source tree; a unit's module is read from the first line of the failed
module's .mod file (link_report.txt FAIL lines, as run_all.sh builds allfiles.txt).
Output resid68.json = {n, classes: {name: class}, counts: {class: n}, detail: {name: {defined_in,
at_other (file: categories), at_own, direct_calls, declared_in, examples}}}. Needs the link-layer
bitcode (heavy, several minutes: llvm-dis of every link-layer file)."""
import collections
import json
import os
import re
import subprocess
from multiprocessing import Pool

from at_only import BA, SYM, cat
from common import (ALLF, DIS16, E, NPROC, RESULTS, OUTDIR, SRC_MARK, outpath, relunit,
                    unit_root)

DEF_RE = re.compile(r'^define[^@]*@([\w.$]+)\(', re.M)
DECL_RE = re.compile(r'^declare[^@]*@([\w.$]+)\(', re.M)
EXPORT_ARTEFACTS = {'export_addressable', 'ksymtab', 'llvm_used', 'global_ptrtoint', 'icmp',
                    'bitcast_direct_call'}


def names():
    p = f'{OUTDIR}/wl_ext.json'
    x = json.load(open(p if os.path.exists(p) else f'{RESULTS}/wl_ext.json'))
    return sorted(set(x['ext_link_unrecovered']) | set(x['defined_link_unrecovered']))


NAMES = names()
CALL_RE = {fn: re.compile(r'\b(call|invoke)\b[^\n]*@' + re.escape(fn) + r'\(') for fn in NAMES}
NAMESET = set(NAMES)


def work(f):
    ll = BA.sub('blockaddress(BA)', subprocess.run([DIS16, '-o', '-', f], capture_output=True,
                                                   text=True, timeout=900).stdout)
    defined = NAMESET & set(DEF_RE.findall(ll))
    declared = NAMESET & set(DECL_RE.findall(ll))
    if not defined and not declared:
        return None
    uses = collections.defaultdict(list)
    calls = collections.Counter()
    for line in ll.split('\n'):
        if line.startswith('!') or line.startswith(';'):
            continue
        for a in SYM.findall(line):
            if a in NAMESET:
                uses[a].append(line.strip()[:220])
        for fn in defined | declared:
            if CALL_RE[fn].search(line):
                calls[fn] += 1
    base = relunit(f) if SRC_MARK in f else os.path.basename(f)
    out = {}
    for fn in defined | declared:
        cats = dict(collections.Counter(cat(l, fn) for l in uses.get(fn, [])))
        out[fn] = dict(file=base, defined=fn in defined, calls=calls[fn], cats=cats,
                       lines=uses.get(fn, [])[:3])
    return out


def failed_module_units(files):
    """{failed .mod: {relative unit paths}} from link_report.txt and the .mod files of the tree."""
    units = [f for f in files if SRC_MARK in f]
    if not units:
        return {}
    root = unit_root(units)
    rep = f"{E('FPEA_LINKBC', '')}/link_report.txt"
    if not os.path.exists(rep):
        rep = f'{RESULTS}/link_report_nosan14.txt'
    mods = {}
    for line in open(rep):
        if line.startswith('FAIL'):
            mod = line.split()[1]
            objs = open(f'{root}{mod}').read().split('\n')[0].split()
            mods[mod] = {f'{os.path.dirname(o)}/.{os.path.basename(o)}.bc' for o in objs}
    return mods


def main():
    files = [l.strip() for l in open(ALLF) if l.strip()]
    per = collections.defaultdict(list)
    fmu = failed_module_units(files)

    def mods_of(name):
        """Module(s) of a link-layer file name: the linked module itself, or the failed module(s)
        whose .mod lists the replacement unit."""
        if '/' in name:
            return {m for m, us in fmu.items() if name in us} or {name}
        return {name}

    with Pool(NPROC) as p:
        for r in p.imap_unordered(work, files, chunksize=4):
            if r:
                for fn, d in r.items():
                    per[fn].append(d)
    classes, detail = {}, {}
    for fn in NAMES:
        rows = per.get(fn, [])
        defined_in = sorted(d['file'] for d in rows if d['defined'])
        at = lambda d: {k: v for k, v in d['cats'].items() if k not in EXPORT_ARTEFACTS}
        at_other = {d['file']: at(d) for d in rows if not d['defined'] and at(d)}
        at_own = {d['file']: at(d) for d in rows if d['defined'] and at(d)}
        def_mods = set().union(*(mods_of(x) for x in defined_in)) if defined_in else set()
        if not defined_in:
            c = 'not_defined'
        elif any(not (mods_of(x) & def_mods) for x in at_other):
            c = 'inter_module'
        elif at_other:
            c = 'unlinked_module'
        elif at_own:
            c = 'own_module_only'
        else:
            c = 'direct_call_only'
        classes[fn] = c
        detail[fn] = dict(defined_in=defined_in, at_other=at_other, at_own=at_own,
                          direct_calls=sum(d['calls'] for d in rows),
                          declared_in=sum(1 for d in rows if not d['defined']),
                          examples={d['file']: d['lines'] for d in rows
                                    if d['file'] in at_other or d['file'] in at_own})
    counts = dict(collections.Counter(classes.values()))
    print('names', len(NAMES), 'link-layer files', len(files), 'classes', counts)
    for fn in NAMES:
        print(f'  {fn:40} {classes[fn]:18} defined_in {len(detail[fn]["defined_in"])}'
              f' at_other {len(detail[fn]["at_other"])} at_own {len(detail[fn]["at_own"])}'
              f' direct_calls {detail[fn]["direct_calls"]}')
    json.dump(dict(n=len(NAMES), classes=classes, counts=counts, detail=detail),
              open(outpath('resid68.json'), 'w'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()

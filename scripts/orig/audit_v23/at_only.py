#!/usr/bin/env python3
"""Exhaustive tagging of the AT-only cases of Section 3.7 / Supplementary Table S2.

For every link-layer file (allfiles.txt): the functions that are defined (after the Section 3.4
filter), not FPEA entry points, and whose symbol appears as a value anywhere except its own
define/declare and the callee position of a direct call (blockaddress and metadata excluded) =
address-taken only. Every use line is categorised and each function gets one tag:
export_addressable_only (16,266), select_phi_ret(+) (205), call_arg(+) (80: argument of a call
through a function pointer), icmp_only / export+icmp+bitcastcall (4 + 1 = the 5 icmp cases).
Output at_only.json = {n, tags, rows: [file, fn, {category: count}, up to 4 use lines]} and
at_only_sample50.json (seed 2026). Needs the link-layer bitcode (heavy, several minutes)."""
import collections
import json
import os
import random
import re
import subprocess
from multiprocessing import Pool

from common import ALLF, DEFINE_RE, DIS16, LINKOUT, NPROC, outpath

BA = re.compile(r'blockaddress\(@[\w.$]+,\s*%[\w.$]+\)')
SYM = re.compile(r'(?<![\w.])@([\w.$]+)(?![\w.(])')
# the same name filter with the clone suffix anchored at the end (link-layer variant used in 2026-11)
CONTAM = re.compile(r'(\.(constprop|isra|part|cold)(\.\d+)?$|^asan\.|^__asan|^kasan\.|^__ubsan'
                    r'|^ubsan\.|^__bpf_trace_|^trace_event_raw_event_|^perf_trace_'
                    r'|^trace_raw_output_|^__traceiter_|^__probestub_|^rcu_lock_|^local_bh_'
                    r'|^__local_bh_|^llvm\.|^__cfi_|^__pfx_|^__x86_indirect|^__sanitizer_cov)')


def key(f):
    return f'{LINKOUT}/{f.replace("/", "_")}.json'


def cat(line, fn):
    L = line.strip()
    if L.startswith('@'):
        g = L.split('=')[0].strip()
        if 'addressable' in g:
            return 'export_addressable'
        if g.startswith('@__ksymtab') or g.startswith('@__kcrctab'):
            return 'ksymtab'
        if g.startswith('@llvm.used') or g.startswith('@llvm.compiler.used'):
            return 'llvm_used'
        if 'ptrtoint' in L:
            return 'global_ptrtoint'
        if re.match(r'@[\w.$]+\s*=\s*(internal |private |dso_local |hidden |weak |linkonce\w* '
                    r'|unnamed_addr |local_unnamed_addr |external )*(alias|ifunc)\b', L):
            return 'alias_ifunc'
        return 'global_init_other'
    if re.match(r'(%\S+\s*=\s*)?icmp\b', L):
        return 'icmp'
    if re.search(r'\bcall\b.*bitcast \([^)]*@' + re.escape(fn) + r'\b[^)]*\)\(', L):
        return 'bitcast_direct_call'
    if re.search(r'\b(call|invoke)\b', L):
        return 'call_arg'
    if re.match(r'store\b', L):
        return 'store'
    if re.match(r'(%\S+\s*=\s*)?(select|phi)\b', L) or re.match(r'ret\b', L):
        return 'select_phi_ret'
    if re.match(r'(%\S+\s*=\s*)?ptrtoint\b', L) or 'ptrtoint' in L:
        return 'ptrtoint_inst'
    return 'other'


def work(f):
    try:
        j = json.load(open(key(f)))
    except Exception:
        return None
    F = set(j['entries'])
    ll = BA.sub('blockaddress(BA)', subprocess.run([DIS16, '-o', '-', f], capture_output=True,
                                                   text=True, timeout=900).stdout)
    clean = {x for x in DEFINE_RE.findall(ll) if not CONTAM.search(x)}
    uses = collections.defaultdict(list)
    for line in ll.split('\n'):
        if line.startswith('!') or line.startswith(';'):
            continue
        for a in SYM.findall(line):
            if a in clean and a not in F:
                uses[a].append(line.strip()[:220])
    out = []
    for fn, lines in uses.items():
        cats = collections.Counter(cat(l, fn) for l in lines)
        out.append((os.path.basename(f), fn, dict(cats), lines[:4]))
    return out


def tag(c):
    ks = set(c)
    if ks == {'export_addressable'}:
        return 'export_addressable_only'
    if ks <= {'export_addressable', 'ksymtab', 'llvm_used', 'global_ptrtoint'}:
        return 'export_artifacts_only'
    if ks == {'icmp'}:
        return 'icmp_only'
    if ks == {'bitcast_direct_call'}:
        return 'bitcast_direct_call_only'
    if ks <= {'export_addressable', 'ksymtab', 'llvm_used', 'global_ptrtoint', 'icmp',
              'bitcast_direct_call'}:
        return 'export+icmp+bitcastcall'
    for k, t in (('global_init_other', 'global_init_other(+)'), ('store', 'store(+)'),
                 ('call_arg', 'call_arg(+)'), ('select_phi_ret', 'select_phi_ret(+)'),
                 ('alias_ifunc', 'alias_ifunc(+)')):
        if k in ks:
            return t
    return 'other:' + '+'.join(sorted(ks))


def main():
    files = [l.strip() for l in open(ALLF) if l.strip()]
    rows = []
    with Pool(NPROC) as p:
        for r in p.imap_unordered(work, files, chunksize=4):
            if r:
                rows += r
    print('AT-only (file, function) pairs:', len(rows))
    T = collections.Counter(tag(c) for _, _, c, _ in rows)
    for k, v in T.most_common():
        print(f'  {k:32} {v}')
    rows.sort(key=lambda r: (r[0], r[1]))
    json.dump(dict(n=len(rows), tags=dict(T), rows=rows), open(outpath('at_only.json'), 'w'),
              ensure_ascii=False)
    random.seed(2026)
    json.dump(random.sample(rows, 50), open(outpath('at_only_sample50.json'), 'w'),
              ensure_ascii=False, indent=1)
    print('sample 50 saved')


if __name__ == '__main__':
    main()

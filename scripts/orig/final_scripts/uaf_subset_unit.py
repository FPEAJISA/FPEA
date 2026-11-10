#!/usr/bin/env python3
"""(b) UAF-related subset, recomputed at the unit layer (5.17.11 LLVM14 nosan).

Applies the classification logic of scale_uaf2.py (not included in the public artifact) to the
original FPEA/UAFX outputs, per unit listed in /tmp/units.txt:
  missed = FPEA entry points - UAFX original-binary entry points (per unit)
  free_reachable: a free call in the function body or in a 1-hop callee
  shared_v1: global access / shared_v2: globals accessed by 2 or more entry points (strict)
Inputs: /tmp/u_fpea/<unit>.json (FPEA entries), <scratch>/rw_5.17.11/<unit>.txt (UAFX entries),
the unit .bc files (llvm-dis).  Output: a summary on stdout and
/home/user/fpea_gt/final/uaf_subset_unit.json.  Invoked as `python3 uaf_subset_unit.py [filter]`
(an optional substring restricts the units).
"""
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from multiprocessing import Pool

DIS = '/usr/bin/llvm-dis-14'
SP = '/tmp/claude-1000/-home-user-fpea-gt/beb7f00d-7da4-4363-8809-fde4eb5531af/scratchpad'
FPEA_DIR = '/tmp/u_fpea'
UAFX_DIR = SP + '/rw_5.17.11'
UNITS_FILE = '/tmp/units.txt'
OUT_JSON = '/home/user/fpea_gt/final/uaf_subset_unit.json'
POOL_SIZE = 14
CHUNKSIZE = 8
SET_LIMIT = 80          # name sets are stored only for entry sets smaller than this
CASE_UNITS = ('tlclk', 'docg3')   # units whose per-unit result is stored as a case
FREE_FN = re.compile(r'@(kfree|kmem_cache_free|kfree_sensitive|kvfree|kzfree|vfree|free_pages|__free_pages|dma_free|devm_kfree|put_device|kfree_skb|consume_skb|free_netdev|free_irq|usb_free_urb|free_page)\b')
DEFINE_RE = re.compile(r'^define[^@]*@([\w.$]+)\(')
GLOBAL_DEF_RE = re.compile(
    r'^@([\w.$]+)\s*=\s*(?:internal\s+|dso_local\s+|external\s+|private\s+|hidden\s+|weak\s+|common\s+)*(?:unnamed_addr\s+|local_unnamed_addr\s+)*global\s',
    re.M)
GLOBAL_REF_RE = re.compile(r'(?<![\w.])@([\w.$]+)(?![\w.(])')
CALL_RE = re.compile(r'\bcall[^@\n]*@([\w.$]+)\(')
# compiler-generated / non-object globals that are not shared-object candidates
NON_OBJECT_PREFIXES = ('.str', '__UNIQUE_ID', 'llvm.', '__func__', '__param', '__mod_',
                       '__exitcall', '__initcall', '__this_module', '__addressable',
                       '__already_done', '__key', '__ksymtab', '__kstrtab', '__crc')
AGG_KEYS = ('n', 'free', 'shared_v1', 'shared_v2', 'any_v1', 'any_v2')


def parse_functions(ll):
    """{function name -> body text} of every `define` in the IR."""
    funcs = {}
    cur = None
    buf = []
    for line in ll.split('\n'):
        m = DEFINE_RE.match(line)
        if m:
            if cur:
                funcs[cur] = '\n'.join(buf)
            cur = m.group(1)
            buf = [line]
        elif cur is not None:
            buf.append(line)
            if line == '}':
                funcs[cur] = '\n'.join(buf)
                cur = None
                buf = []
    return funcs


def is_object_global(g):
    """Shared-object candidates = mutable globals (global) only. Strings, constants (constant)
    and compiler-generated globals are excluded."""
    return not (g.startswith(NON_OBJECT_PREFIXES) or '.descriptor' in g)


def read_entries(unit_name):
    """FPEA entry points of a unit, or None if the FPEA output is missing."""
    try:
        return set(json.load(open(f'{FPEA_DIR}/{unit_name}.json'))['entries'])
    except Exception:
        return None


def read_baseline(unit_name):
    """UAFX original-binary entry points of a unit (empty if the file is missing)."""
    base = set()
    p = f'{UAFX_DIR}/{unit_name}.txt'
    if os.path.exists(p):
        for l in open(p, errors='replace'):
            q = l.strip().split(':')
            if len(q) >= 2:
                base.add(q[1])
    return base


def free_reach(funcs, fn):
    """True if fn or one of its direct callees calls a free function."""
    body = funcs.get(fn, '')
    if FREE_FN.search(body):
        return True
    for c in CALL_RE.findall(body):
        if c in funcs and FREE_FN.search(funcs[c]):
            return True
    return False


def calc(funcs, gdef, S):
    """Free-reachable / shared-global counts over the entry set S."""
    glob_access = defaultdict(set)
    fn_globals = {}
    for f in S:
        body = funcs.get(f, '')
        gs = {g for g in GLOBAL_REF_RE.findall(body) if g in gdef}
        fn_globals[f] = gs
        for g in gs:
            glob_access[g].add(f)
    multi = {g for g, fs in glob_access.items() if len(fs) >= 2}
    fr = {f for f in S if free_reach(funcs, f)}
    s1 = {f for f in S if fn_globals[f]}
    s2 = {f for f in S if fn_globals[f] & multi}
    return dict(n=len(S), free=len(fr), shared_v1=len(s1), shared_v2=len(s2),
                any_v1=len(fr | s1), any_v2=len(fr | s2),
                free_set=sorted(fr) if len(S) < SET_LIMIT else None,
                s2_set=sorted(s2) if len(S) < SET_LIMIT else None)


def one(bc):
    """Per-unit result: counts on two bases, all entry points (E) and missed (M)."""
    n = bc.replace('/', '_')
    e = read_entries(n)
    if e is None:
        return None
    base = read_baseline(n)
    # computed on two bases: all entry points (E) and missed (M)
    try:
        ll = subprocess.run([DIS, '-o', '-', bc], capture_output=True, text=True,
                            timeout=300).stdout
    except Exception:
        return None
    funcs = parse_functions(ll)
    gdef = set(g for g in GLOBAL_DEF_RE.findall(ll) if is_object_global(g))
    M = e - base
    return dict(unit=bc, defined=len(funcs), E=calc(funcs, gdef, e), M=calc(funcs, gdef, M),
                base=len(base & e))


def read_units():
    units = [l.strip() for l in open(UNITS_FILE) if l.strip()]
    if len(sys.argv) > 1:
        units = [u for u in units if sys.argv[1] in u]
    return units


def aggregate(units):
    """Run `one` over all units in a pool; return (aggregate counters, stored cases)."""
    agg = defaultdict(int)
    per = {}
    with Pool(POOL_SIZE) as p:
        for r in p.imap_unordered(one, units, chunksize=CHUNKSIZE):
            if not r:
                agg['fail'] += 1
                continue
            agg['units'] += 1
            agg['defined'] += r['defined']
            agg['base'] += r['base']
            for k in ('E', 'M'):
                for kk in AGG_KEYS:
                    agg[f'{k}_{kk}'] += r[k][kk]
            if any(case in r['unit'] for case in CASE_UNITS):
                per[r['unit']] = r
    return agg, per


def print_summary(a, per):
    print(f"units {a['units']} fail {a['fail']} defined {a['defined']} FPEA {a['E_n']} "
          f"baseline∩FPEA {a['base']} missed {a['M_n']}")
    for k in ('E', 'M'):
        print(f"[{k}] free {a[k+'_free']} shared_v1 {a[k+'_shared_v1']} "
              f"shared_v2 {a[k+'_shared_v2']} any_v1 {a[k+'_any_v1']} "
              f"({a[k+'_any_v1']/a[k+'_n']*100:.1f}%) any_v2 {a[k+'_any_v2']} "
              f"({a[k+'_any_v2']/a[k+'_n']*100:.1f}%)")
    for u, r in per.items():
        print(u, json.dumps(r['E'], ensure_ascii=False)[:600])


def main():
    units = read_units()
    agg, per = aggregate(units)
    out = dict(agg=dict(agg), cases=per)
    with open(OUT_JSON, 'w') as fp:
        json.dump(out, fp, indent=1)
    print_summary(agg, per)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Whitelist-only pairs of Section 5.3 / Supplementary Table S3, step 1 (heavy).

UAFX unit output (rw_5.17.11) minus FPEA unit output (rf_5.17.11) = 987 (unit, function) pairs.
Each pair is classified in the unit's IR (llvm-dis 14): the function is `define`d in the unit
(289, all IOCTL_CAND) or only `declare`d there (698 = IOCTL_CAND 547 + INT_HANDLER_T 151, an
external symbol reported in a client unit). Output wl_only.json with the full pair lists; wl_ext.py
continues from it without bitcode."""
import collections
import json
import os
import re
import subprocess
from multiprocessing import Pool

from common import DIS14, NPROC, RF, RW, outpath, relunit, rf_json, units

DECL_RE = re.compile(r'^declare[^@]*@([\w.$]+)\(', re.M)
DEF_RE = re.compile(r'^define[^@]*@([\w.$]+)\(', re.M)


def cls(a):
    u, fns = a
    ll = subprocess.run([DIS14, '-o', '-', u], capture_output=True, text=True, timeout=600).stdout
    dec = set(DECL_RE.findall(ll))
    dfn = set(DEF_RE.findall(ll))
    return [(u, fn, 'defined' if fn in dfn else 'declared' if fn in dec else 'other') for fn in fns]


def main():
    U = units()
    W = set()
    Wkind = {}
    for u in U:
        p = f'{RW}/{u.replace("/", "_")}.txt'
        if not os.path.exists(p):
            continue
        for l in open(p, errors='replace'):
            q = l.strip().split(':')
            if len(q) >= 2 and q[1]:
                W.add((u, q[1]))
                Wkind[(u, q[1])] = q[0]
    F = set()
    for u in U:
        p = rf_json(u, RF)
        if os.path.exists(p):
            for fn in json.load(open(p))['entries']:
                F.add((u, fn))
    print('WL (unit, function) pairs', len(W), 'WL unique names', len({fn for u, fn in W}),
          'WL∩FPEA', len(W & F), 'WL∖FPEA', len(W - F))
    todo = collections.defaultdict(list)
    for u, fn in W - F:
        todo[u].append(fn)
    rows = []
    with Pool(NPROC) as p:
        for r in p.imap_unordered(cls, list(todo.items()), chunksize=4):
            rows += r
    rows.sort()
    C = collections.Counter((Wkind[(u, fn)], c) for u, fn, c in rows)
    print('WL∖FPEA breakdown (kind|class):', dict(C))
    ext = [(u, fn) for u, fn, c in rows if c == 'declared']
    extfn = collections.Counter(fn for u, fn in ext)
    print('external (declared) pairs', len(ext), 'unique names', len(extfn),
          '| most redundantly reported:', extfn.most_common(8))
    Fnames = {fn for u, fn in F}
    print('external unique names that FPEA identifies in their own defining unit:',
          sum(1 for fn in extfn if fn in Fnames), '/', len(extfn))
    defined = [(u, fn) for u, fn, c in rows if c == 'defined']
    print('defined but not FPEA:', collections.Counter(Wkind[(u, fn)] for u, fn in defined),
          'unique names', len({fn for u, fn in defined}))
    json.dump(dict(W_pairs=len(W), W_unique=len({fn for u, fn in W}), inter=len(W & F),
                   wl_only=len(W - F), decomp={f'{a}|{b}': n for (a, b), n in C.items()},
                   ext_pairs=len(ext), ext_unique=len(extfn), ext_top=extfn.most_common(20),
                   ext_in_fpea_elsewhere=sum(1 for fn in extfn if fn in Fnames),
                   defined_not_fpea=len(defined), defined_unique=len({fn for u, fn in defined}),
                   # unit paths relative to the source tree (drivers/…), so that a re-run under
                   # another root compares equal
                   rows=[[relunit(u), fn, Wkind[(u, fn)], c] for u, fn, c in rows]),
              open(outpath('wl_only.json'), 'w'), indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()

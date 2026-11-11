#!/usr/bin/env python3
"""Reconstruct the stage-2 negative pool of Section 5.2 / Supplementary S11.

Stage 1 of sample_gt_unit.py draws 500 units (seed 913); the pool is the union of their
non-entry-point functions: llvm-dis `define` minus the Section 3.4 filter minus the FPEA entry
points. Output recon_pool2.json = {pool_total, zero_units, max_unit, M: {unit: size},
pool: {unit: [function names]}, sample_in_pool}. The paper quotes pool 3,071 over 500 units
(122 with 0, max 100). The earlier recon_pool.py keyed units by basename and collided on 10
duplicate names ("490 valid units / pool 3,021"); this version keys by the unit path relative to
the source tree (drivers/…; absolute until 2026-11-11). Needs the bitcode tree (heavy)."""
import json
import subprocess
from multiprocessing import Pool

from common import (CONTAM, DEFINE_RE, DIS16, GT, NPROC, module_name, outpath, relunit, rf_json,
                    selected_units)


def neg(f):
    F = set(json.load(open(rf_json(f)))['entries'])
    ll = subprocess.run([DIS16, '-o', '-', f], capture_output=True, text=True, timeout=300).stdout
    clean = {x for x in DEFINE_RE.findall(ll) if not CONTAM.search(x)}
    return (f, sorted(clean - F))


def main():
    sel = selected_units()
    res = {}
    with Pool(NPROC) as p:
        for f, lst in p.imap_unordered(neg, sel, chunksize=6):
            res[relunit(f)] = lst
    M = {f: len(l) for f, l in res.items()}
    print('units', len(M), 'pool', sum(M.values()), 'zero',
          sum(1 for v in M.values() if v == 0), 'max', max(M.values()))
    de = {f: json.load(open(rf_json(f)))['defined'] - len(json.load(open(rf_json(f)))['entries'])
          for f in sel}
    print('sum defined-entries', sum(de.values()), 'units differ',
          sum(1 for f in sel if de[f] != M[relunit(f)]))
    d = json.load(open(GT))
    poolset = {(fn, module_name(f)) for f, l in res.items() for fn in l}
    inpool = sum(1 for fn, m in d['neg'] if (fn, m) in poolset)
    print('sample200 in pool', inpool)
    json.dump(dict(pool_total=sum(M.values()), units=len(M),
                   zero_units=sum(1 for v in M.values() if v == 0), max_unit=max(M.values()),
                   sample_in_pool=inpool, M=M, pool=res),
              open(outpath('recon_pool2.json'), 'w'))


if __name__ == '__main__':
    main()

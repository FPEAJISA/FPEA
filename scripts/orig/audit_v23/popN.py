#!/usr/bin/env python3
"""Negative population |N| of Section 5.2 (Supplementary S11).

For every 5.17.11 unit: the number of `define`d functions in the bitcode (llvm-dis), the number
left after the Section 3.4 filter, and both minus the FPEA entry points. The paper uses the
post-filter value: N_clean = 236,515 - 129,967 = 106,548 (the pre-filter 112,856 is reported in
Section 5.10 only as the sensitivity value). Output: popN.json = {unit: [define_all, define_clean,
N_all, N_clean, json_defined]} plus a 'totals' entry. Needs the bitcode tree (heavy)."""
import json
import subprocess
from multiprocessing import Pool

from common import CONTAM, DEFINE_RE, DIS16, NPROC, outpath, rf_json, units


def neg(f):
    j = json.load(open(rf_json(f)))
    F = set(j['entries'])
    ll = subprocess.run([DIS16, '-o', '-', f], capture_output=True, text=True, timeout=600).stdout
    alld = set(DEFINE_RE.findall(ll))
    clean = {x for x in alld if not CONTAM.search(x)}
    return (f, len(alld), len(clean), len(alld - F), len(clean - F), j['defined'])


def main():
    res = {}
    with Pool(NPROC) as p:
        for r in p.imap_unordered(neg, units(), chunksize=20):
            res[r[0]] = list(r[1:])
    tot = dict(units=len(res),
               define_all=sum(v[0] for v in res.values()),
               define_clean=sum(v[1] for v in res.values()),
               N_all=sum(v[2] for v in res.values()),
               N_clean=sum(v[3] for v in res.values()),
               json_defined=sum(v[4] for v in res.values()))
    print('units', tot['units'], 'define_all', tot['define_all'], 'define_clean',
          tot['define_clean'], 'json_defined', tot['json_defined'], 'N_all', tot['N_all'],
          'N_clean', tot['N_clean'])
    json.dump(dict(totals=tot, units=res), open(outpath('popN.json'), 'w'))


if __name__ == '__main__':
    main()

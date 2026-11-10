"""Exclusive decomposition of the link-layer FPEA entry points by signal (C1/C2/C3·C5r/C4 only).

Reuses measure_c5r.job (signals + baseline tool output per unit) and additionally records
the address-taken set, the functions used in icmp and one store context per C4-only function.
Invoked as `python3 decomp.py > decomp.log` from this folder; writes decomp.json.
"""
import os
import re
import subprocess
import random
import json
from multiprocessing import Pool
from collections import Counter

from measure_c5r import DIS, SYM, job, list_input_files

# Category labels are stored keys in decomp.json, kept verbatim:
# 'with C1' = has C1, 'C2 (no C1)' = C2 without C1,
# 'C3/C5r (no C1/C2)' = C3/C5r without C1/C2, 'C4 only' = C4 only.
CAT_ORDER = ('with C1', 'C2 (no C1)', 'C3/C5r (no C1/C2)', 'C4 only')


def work(p):
    """Pool worker for unit p: (unit name, defined count, address-taken set, signals,
    baseline entry points, functions used in icmp, {function: first store line})."""
    r = job(p)
    if not r:
        return None
    path, c, dec, sig, ctx, W = r
    ll = subprocess.run([DIS, '-o', '-', p], capture_output=True, text=True).stdout
    at = set()
    icmp = set()
    c4ctx = {}
    for line in ll.split('\n'):
        if line.startswith('!') or line.startswith(';'):
            continue      # skip metadata
        L = line.strip()
        for a in SYM.findall(line):
            if a in c:
                at.add(a)
                if re.match(r'(%\S+\s*=\s*)?icmp\b', L):
                    icmp.add(a)
                if L.startswith('store') and a not in c4ctx:
                    c4ctx[a] = L[:110]
    return os.path.basename(path), len(c), at, sig, W, icmp, c4ctx


def main():
    """Aggregate the decomposition over all units, print it and write decomp.json."""
    files = list_input_files()
    D = AT = F = 0                  # defined / address-taken / FPEA
    cat = Counter()                 # exclusive category -> count
    Wn = Iall = Icons = 0           # baseline entry points, ∩ FPEA, ∩ conservative
    c4icmp = 0                      # C4-only functions also used in icmp
    samp = []                       # (function, unit, store context) of C4-only functions
    with Pool(14) as pl:
        for r in pl.imap_unordered(work, files, chunksize=8):
            if not r:
                continue
            m, d, at, sig, W, icmp, c4ctx = r
            D += d
            AT += len(at)
            F += len(sig)
            cons = set()
            for f, s in sig.items():
                if 'C1' in s:
                    k = 'with C1'
                elif 'C2' in s:
                    k = 'C2 (no C1)'
                elif s & {'C3', 'C5'}:
                    k = 'C3/C5r (no C1/C2)'
                else:
                    k = 'C4 only'
                cat[k] += 1
                if k != 'C4 only':
                    cons.add(f)
                else:
                    if f in icmp:
                        c4icmp += 1
                    if len(samp) < 400:
                        samp.append((f, m[:40], c4ctx.get(f, '')))
            for fn in W:
                Wn += 1
                if fn in sig:
                    Iall += 1
                if fn in cons:
                    Icons += 1
    C = F - cat['C4 only']            # conservative lower bound
    print(f"defined functions (population) {D:7}")
    print(f"address-taken (upper bound) {AT:7}  {AT/D*100:5.1f}%"
          f"   note: uses other than direct calls, metadata excluded")
    print(f"FPEA C5r                  {F:7}  {F/D*100:5.1f}%")
    print(f"conservative lower bound (excl. C4-only) {C:7}  {C/D*100:5.1f}%")
    print("\nexclusive decomposition by signal (over FPEA entry points)")
    for k in CAT_ORDER:
        print(f"  {k:22} {cat[k]:7}  {cat[k]/F*100:5.1f}%")
    print(f"\nC4-only functions also used in comparisons (icmp) (state-machine indicator):"
          f" {c4icmp}  ({c4icmp/max(cat['C4 only'],1)*100:.1f}%)")
    print(f"\nbaseline {Wn}: FPEA∩={Iall}  conservative∩={Icons}")
    print(f"miss rate: FPEA {(F-Iall)/F*100:.2f}%   conservative {(C-Icons)/C*100:.2f}%")
    random.seed(3)
    print("\nC4-only sample of 12:")
    for f, m, L in random.sample(samp, 12):
        print(f"  {f:34} [{m}]  {L[:75]}")
    result = dict(D=D, AT=AT, F=F, cons=C, cat=dict(cat), c4icmp=c4icmp, W=Wn, Iall=Iall,
                  Icons=Icons)
    with open('decomp.json', 'w') as fh:
        json.dump(result, fh, indent=1)


if __name__ == '__main__':
    main()

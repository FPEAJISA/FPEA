"""Address-taken vs FPEA (C5r) at the link layer, and the share admitted only via blockaddress.

Reuses measure_c5r.analyze_text on the IR text of each unit, once as is and once with every
blockaddress(@f, %bb) operand neutralised, and tallies the usage forms of address-taken
functions that FPEA does not admit.
Invoked as `python3 atfinal.py > atfinal.log` from this folder; writes atfinal.json.
"""
import re
import subprocess
import json
from multiprocessing import Pool
from collections import Counter

from measure_c5r import DIS, EXP, SYM, analyze_text, list_input_files

BA = re.compile(r'blockaddress\(@[\w.$]+,\s*%[\w.$]+\)')


def w(p):
    """Pool worker for unit p: (defined count, address-taken set, FPEA set,
    FPEA set without blockaddress, {function: {usage kind}})."""
    ll = subprocess.run([DIS, '-o', '-', p], capture_output=True, text=True, timeout=900).stdout
    c, dec, sig, ctx = analyze_text(ll)
    c2, dec2, sig2, ctx2 = analyze_text(BA.sub('blockaddress(BA)', ll))   # ignore blockaddress
    at = set()
    kinds = {}
    for line in ll.split('\n'):
        if line.startswith('!') or line.startswith(';'):
            continue
        L = line.strip()
        for m in SYM.finditer(line):
            a = m.group(1)
            if a not in c:
                continue
            at.add(a)
            if line.startswith('@') and EXP.search(line.split('=')[0]):
                k = 'export-artifact'
            elif 'blockaddress(@' + a in line:
                k = 'blockaddress'
            elif line.startswith('@'):
                k = 'global'
            elif re.match(r'(%\S+\s*=\s*)?icmp\b', L):
                k = 'icmp'
            elif re.match(r'(%\S+\s*=\s*)?(select|phi)\b', L):
                k = 'select/phi'
            elif L.startswith('store'):
                k = 'store'
            elif re.match(r'ret\b', L):
                k = 'ret'
            elif re.search(r'\bcall\b', L):
                k = 'callarg'
            else:
                k = 'other'
            kinds.setdefault(a, set()).add(k)
    return len(c), at, set(sig), set(sig2), kinds


def main():
    """Aggregate over all units, print the summary and write atfinal.json."""
    files = list_input_files()
    D = AT = F = F2 = 0             # defined / address-taken / FPEA / FPEA without blockaddress
    diff = Counter()                # usage-form combinations of AT − FPEA
    baonly = []                     # examples admitted only via blockaddress
    with Pool(14) as pl:
        for d, at, s, s2, kinds in pl.imap_unordered(w, files, chunksize=8):
            D += d
            AT += len(at)
            F += len(s)
            F2 += len(s2)
            for a in at - s:
                diff[' + '.join(sorted(kinds[a]))] += 1
            for a in s - s2:
                if len(baonly) < 6:
                    baonly.append(a)
    print(f"defined functions {D}")
    print(f"address-taken    {AT}  ({AT/D*100:.1f}%)")
    print(f"FPEA C5r         {F}  ({F/D*100:.1f}%)")
    print(f"FPEA C5r − blockaddress FPs   {F2}  ({F2/D*100:.1f}%)"
          f"   → admitted only via blockaddress {F-F2}  e.g.: {baonly}")
    print(f"\nusage forms of AT − FPEA = {AT-F}")
    for k, n in diff.most_common(10):
        print(f"  {k:36} {n:6}  {n/(AT-F)*100:5.1f}%")
    with open('atfinal.json', 'w') as fh:
        json.dump(dict(D=D, AT=AT, F=F, F2=F2, diff=dict(diff)), fh, indent=1)


if __name__ == '__main__':
    main()

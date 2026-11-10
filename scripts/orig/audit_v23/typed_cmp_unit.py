#!/usr/bin/env python3
"""Section 5.5 first axis / Table 12 row 1: fpea14 vs fpea16 on the same LLVM 14 bitcode.

Compares rf14_5.17.11 (fpea14 --unit, typed pointers kept) with rf_5.17.11 (fpea16 --unit,
pointers promoted to opaque) for every unit: entry-point totals, units whose entry sets differ,
functions only in one side, functions whose signal labels differ, units whose defined count
differs. Output typed_mode_cmp.json (light; the fpea14 outputs are produced by run-fpea)."""
import json
import os

from common import RF, RF14, outpath, rf_json, units


def main():
    n14 = n16 = 0
    diff_units = only14 = only16 = sigdiff = defdiff = missing = 0
    for u in units():
        p14, p16 = rf_json(u, RF14), rf_json(u, RF)
        if not (os.path.exists(p14) and os.path.exists(p16)):
            missing += 1
            continue
        a, b = json.load(open(p14)), json.load(open(p16))
        ea, eb = a['entries'], b['entries']
        n14 += len(ea)
        n16 += len(eb)
        if set(ea) != set(eb):
            diff_units += 1
        only14 += len(set(ea) - set(eb))
        only16 += len(set(eb) - set(ea))
        sigdiff += sum(1 for fn in set(ea) & set(eb) if set(ea[fn]) != set(eb[fn]))
        defdiff += a['defined'] != b['defined']
    out = dict(fpea14=n14, fpea16=n16, diff_units=diff_units, only14=only14, only16=only16,
               sigdiff=sigdiff, defdiff=defdiff, missing=missing)
    print(json.dumps(out))
    json.dump(out, open(outpath('typed_mode_cmp.json'), 'w'))


if __name__ == '__main__':
    main()

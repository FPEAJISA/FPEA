"""Pure unit-layer comparison of FPEA with the UAFX baseline, focused on C2 (module lifecycle).

Reads $FPEA_TMP/units.txt (unit list), $FPEA_TMP/u_fpea/<unit>.json (FPEA output) and
$FPEA_TMP/u_wl/<unit>.txt (UAFX baseline).  Prints the summary to stdout and writes
c2_evidence.json.  Invoked as `python3 c2_evidence.py` from the fpea_pass folder.
"""
import json
import os
from collections import Counter
from multiprocessing import Pool

# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
HOME_ROOT = os.environ.get('FPEA_HOME') or os.path.expanduser('~')
TMP_ROOT = os.environ.get('FPEA_TMP', '/tmp')

UNITS_FILE = f'{TMP_ROOT}/units.txt'
FPEA_OUT_DIR = f'{TMP_ROOT}/u_fpea/'
WL_OUT_DIR = f'{TMP_ROOT}/u_wl/'
OUT_JSON = 'c2_evidence.json'
POOL_SIZE = 14
CHUNKSIZE = 8
SIGNALS = ('C1', 'C2', 'C3', 'C4', 'C5')


def fpea_json_path(bc):
    """FPEA output JSON for a unit path."""
    return FPEA_OUT_DIR + bc.replace('/', '_') + '.json'


def wl_path(bc):
    """UAFX baseline (whitelist) text file for a unit path."""
    return WL_OUT_DIR + bc.replace('/', '_') + '.txt'


def unit_stats(bc):
    """Pool worker: FPEA totals, signal distribution and relation to the baseline for one unit.

    Returns (fpea count, signal counts, baseline count, baseline covered by FPEA,
    baseline minus FPEA, C2-only count, C2-only also in baseline, baseline kinds).
    """
    if not os.path.exists(fpea_json_path(bc)):
        return None
    entries = json.load(open(fpea_json_path(bc)))['entries']
    entry_set = set(entries)
    sig = Counter()
    c2_only = set()
    for fn, signals in entries.items():
        for x in signals:
            sig[x] += 1
        if set(signals) == {'C2'}:
            c2_only.add(fn)
    baseline = {}
    wl_kinds = Counter()
    if os.path.exists(wl_path(bc)):
        for line in open(wl_path(bc), errors='replace'):
            parts = line.strip().split(':')
            if len(parts) >= 2:
                baseline.setdefault(parts[1], parts[0])
                wl_kinds[parts[0]] += 1
    inter = len(set(baseline) & entry_set)
    wl_minus_fpea = len(set(baseline) - entry_set)
    # are C2 entry points in the baseline (does UAFX catch module lifecycle)
    c2_in_wl = len(c2_only & set(baseline))
    return (len(entry_set), dict(sig), len(baseline), inter, wl_minus_fpea,
            len(c2_only), c2_in_wl, dict(wl_kinds))


def main():
    units = [line.strip() for line in open(UNITS_FILE)]
    fpea_total = 0
    wl_total = inter = wl_minus_fpea = c2_total = c2_in_wl_total = 0
    wl_kinds = Counter()
    sig_total = Counter()
    with Pool(POOL_SIZE) as pool:
        for result in pool.imap_unordered(unit_stats, units, chunksize=CHUNKSIZE):
            if not result:
                continue
            n_fpea, sig, n_wl, n_inter, n_wmf, n_c2, n_c2wl, kinds = result
            fpea_total += n_fpea
            wl_total += n_wl
            inter += n_inter
            wl_minus_fpea += n_wmf
            c2_total += n_c2
            c2_in_wl_total += n_c2wl
            for k, v in sig.items():
                sig_total[k] += v
            for k, v in kinds.items():
                wl_kinds[k] += v

    print("=== Pure unit layer (same conditions as the UAFX authors) ===")
    print(f"FPEA entry points {fpea_total}")
    print(f"signal distribution: "
          + "  ".join(f"{k} {sig_total[k]}({sig_total[k]/fpea_total*100:.1f}%)"
                      for k in SIGNALS))
    print(f"UAFX baseline {wl_total}  kinds: {dict(wl_kinds)}")
    print(f"miss rate (baseline covered by FPEA {inter}, baseline\\FPEA {wl_minus_fpea})")
    print(f"  baseline missed by FPEA: {wl_minus_fpea}")
    print(f"  FPEA missed by baseline: {fpea_total-inter}"
          f"  = {(fpea_total-inter)/fpea_total*100:.2f}%")
    print(f"\n=== ★C2 (module lifecycle) key point ===")
    print(f"C2-only entry points: {c2_total}  ({c2_total/fpea_total*100:.1f}% of FPEA)")
    print(f"  of which also caught by the UAFX baseline: {c2_in_wl_total}")
    caught = 'none' if c2_in_wl_total == 0 else 'only ' + str(c2_in_wl_total)
    print(f"  → UAFX catches {caught} of the module lifecycle entry points")

    summary = dict(fpea=fpea_total, sig=dict(sig_total), wl=wl_total, wl_kinds=dict(wl_kinds),
                   inter=inter, wmf=wl_minus_fpea, miss=(fpea_total-inter)/fpea_total,
                   c2=c2_total, c2_in_wl=c2_in_wl_total)
    with open(OUT_JSON, 'w') as out:
        json.dump(summary, out, indent=1)


if __name__ == '__main__':
    main()

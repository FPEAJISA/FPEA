"""Draw the blinded ground-truth review sample at the unit layer.

Positives: FPEA entry points stratified by signal (C2-only excluded), seed 517.
Negatives: defined functions FPEA did not report, from a shuffled subset of units
(seeds 913 and 31).  Rows are shuffled with seed 9.
Reads /tmp/units.txt and /tmp/u_fpea/<unit>.json; writes gt_review_unit.csv (blinded),
gt_answer_unit.json (answer key) and gt_sample_unit.json.  Invoked as `python3 sample_gt_unit.py`.
"""
import csv
import json
import os
import random
import re
import subprocess
from collections import defaultdict
from multiprocessing import Pool

UNITS_FILE = '/tmp/units.txt'
FPEA_OUT_DIR = '/tmp/u_fpea/'
DIS = os.path.expanduser('~/llvm/build/bin/llvm-dis')
DIS_TIMEOUT = 300
POOL_SIZE = 14
CHUNKSIZE = 6
NEG_UNITS = 500           # units scanned for the negative pool (after shuffling)
NEG_POOL_LIMIT = 50000    # stop scanning once the pool exceeds this
NEG_SAMPLE = 200
QUOTA = {'C1': 80, 'C4only': 70, 'C3': 60, 'C5': 45}
# compiler-generated / instrumentation symbols excluded from the negative pool
CONTAM = re.compile(r'(\.\d+$|\.(constprop|isra|part|cold)\b|^asan\.|^__asan|^kasan\.|^__ubsan|^ubsan\.|^__bpf_trace_|^trace_event_raw_event_|^perf_trace_|^trace_raw_output_|^__traceiter_|^__probestub_|^rcu_lock_|^local_bh_|^__local_bh_|^llvm\.|^__cfi_|^__pfx_|^__x86_indirect|^__sanitizer_cov)')
DEFINE_RE = re.compile(r'^define[^@]*@([\w.$]+)\(', re.M)


def fpea_json_path(bc):
    """FPEA output JSON for a unit path."""
    return FPEA_OUT_DIR + bc.replace('/', '_') + '.json'


def module_name(bc):
    """Module name from the unit file name (`.foo.o.bc` -> `foo`)."""
    return os.path.basename(bc)[1:].replace('.o.bc', '')


def stratum(sig):
    """Sampling stratum of a signal set."""
    s = set(sig)
    if 'C3' in s:
        return 'C3'
    if 'C5' in s:
        return 'C5'
    if 'C4' in s and 'C1' not in s:
        return 'C4only'
    return 'C1'   # C1 or C1+C2 etc.


# ── positives: FPEA entry points, stratified excluding C2 ──
def collect_positives(units):
    """(function, module, sorted signals) for every entry point, grouped by stratum."""
    by_stratum = defaultdict(list)
    for bc in units:
        if not os.path.exists(fpea_json_path(bc)):
            continue
        entries = json.load(open(fpea_json_path(bc)))['entries']
        mod = module_name(bc)
        for fn, signals in entries.items():
            if set(signals) == {'C2'}:
                continue          # C2-only is trivial (ABI) → excluded from review
            sig = tuple(sorted(signals))
            by_stratum[stratum(sig)].append((fn, mod, sig))
    return by_stratum


def sample_positives(by_stratum):
    """Stratified sample (seed 517) in QUOTA order, deduplicated by function name."""
    random.seed(517)
    sample = []
    for k, q in QUOTA.items():
        sample += random.sample(by_stratum[k], min(q, len(by_stratum[k])))
    seen = set()
    positives = []
    for fn, mod, sig in sample:
        if fn in seen:
            continue
        seen.add(fn)
        positives.append((fn, mod, sig))
    return positives


# ── negatives: defined functions FPEA did not report as entry points ──
def neg(bc):
    """Pool worker: (function, module) for clean defined functions not reported by FPEA."""
    if not os.path.exists(fpea_json_path(bc)):
        return []
    entry_set = set(json.load(open(fpea_json_path(bc)))['entries'])
    try:
        ll = subprocess.run([DIS, '-o', '-', bc], capture_output=True, text=True,
                            timeout=DIS_TIMEOUT).stdout
    except Exception:
        return []
    clean = {x for x in DEFINE_RE.findall(ll) if not CONTAM.search(x)}
    mod = module_name(bc)
    return [(fn, mod) for fn in clean - entry_set]


def collect_negative_pool(units):
    """Negative candidates from the first NEG_UNITS of a shuffled unit list (seed 913)."""
    random.seed(913)
    shuffled = units[:]
    random.shuffle(shuffled)
    pool = []
    with Pool(POOL_SIZE) as workers:
        for result in workers.imap_unordered(neg, shuffled[:NEG_UNITS], chunksize=CHUNKSIZE):
            pool += result
            if len(pool) > NEG_POOL_LIMIT:
                break
    return pool


# ── merge, blinded CSV + answer-key mapping ──
def write_outputs(positives, negatives):
    """Shuffle (seed 9), write the blinded CSV, the answer key and the sample record."""
    rows = ([(fn, mod, 'pos', sig) for fn, mod, sig in positives]
            + [(fn, mod, 'neg', []) for fn, mod in negatives])
    random.seed(9)
    random.shuffle(rows)
    answers = {}
    with open('gt_review_unit.csv', 'w', newline='') as out:
        writer = csv.writer(out)
        # CSV header kept verbatim (stored data format): verdict(1/0/?), rule, note
        writer.writerow(['id', 'module', 'function', 'verdict(1/0/?)', 'rule', 'remark'])
        for i, (fn, mod, label, sig) in enumerate(rows, 1):
            gid = f'G{i:03d}'
            writer.writerow([gid, mod, fn, '', '', ''])
            answers[gid] = dict(fn=fn, module=mod, fpea_positive=(label == 'pos'),
                                signals=list(sig))
    with open('gt_answer_unit.json', 'w') as out:
        json.dump(answers, out, indent=1, ensure_ascii=False)
    with open('gt_sample_unit.json', 'w') as out:
        json.dump(dict(pos=positives, neg=negatives, quota=QUOTA), out, ensure_ascii=False)
    return rows


def main():
    units = [line.strip() for line in open(UNITS_FILE)]

    by_stratum = collect_positives(units)
    print("positive stratum populations (excl. C2-only):",
          {k: len(v) for k, v in by_stratum.items()})
    positives = sample_positives(by_stratum)
    print(f"positive sample {len(positives)} (deduplicated)")

    pool = collect_negative_pool(units)
    random.seed(31)
    negatives = random.sample(pool, NEG_SAMPLE)
    print(f"negative sample {len(negatives)} (pool {len(pool)})")

    rows = write_outputs(positives, negatives)
    print(f"gt_review_unit.csv written: {len(rows)} rows"
          f" (positive {len(positives)} + negative {len(negatives)})")


if __name__ == '__main__':
    main()

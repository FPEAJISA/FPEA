"""Reference set re-check: answer-key consistency against the unit FPEA outputs, corrected
stratum weights (strata_pop.json), Wilson confidence intervals, population-corrected recall.
Run with cwd = $FIN ($FPEA_HOME/fpea_gt/final) by run_all.sh derive, after derive_results.py copied
strata_pop.json there: `python3 review_check.py`. Prints the tables and writes
review_check.json into the cwd."""
import csv
import json
import math
import os
from collections import defaultdict

# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
HOME_ROOT = os.environ.get('FPEA_HOME') or os.path.expanduser('~')
TMP_ROOT = os.environ.get('FPEA_TMP', '/tmp')

ANSWER_PATH = f'{HOME_ROOT}/rerun/fpea_pass/gt_answer_unit.json'
UNITS_PATH = f'{TMP_ROOT}/units.txt'          # unit list (setup.py links it to list_5.17.11.txt)
UNIT_FPEA_DIR = f'{TMP_ROOT}/u_fpea/'         # per-unit FPEA json (setup.py links it to rf_5.17.11)
STRATA_POP_PATH = 'strata_pop.json'
RA_PATH = '../expert_pkg/rA.csv'
RB_PATH = '../expert_pkg/rB.csv'
ADJ_PATH = '../expert_pkg/adjudication_17_final.csv'


def read_verdicts(path):
    """Expert CSV -> {id: verdict}."""
    return {r['id']: r['verdict'] for r in csv.DictReader(open(path, encoding='utf-8-sig'))}


def read_adjudication(path):
    """Adjudication CSV -> {id: adjudicated verdict (adjudicated_verdict)}."""
    return {r['id']: r['adjudicated_verdict'] for r in csv.DictReader(open(path, encoding='utf-8'))}


def st(sig):
    """Stratum of a signal list: C3 > C5 > C4only (C4 without C1) > C1."""
    s = set(sig)
    if 'C3' in s:
        return 'C3'
    if 'C5' in s:
        return 'C5'
    if 'C4' in s and 'C1' not in s:
        return 'C4only'
    return 'C1'


def wilson(k, n, z=1.96):
    """Wilson score interval for k successes out of n."""
    if n == 0:
        return (0, 0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def load_unit_signals():
    """{(function, module): sorted signals} from the per-unit FPEA json of every listed unit."""
    units = [l.strip() for l in open(UNITS_PATH)]
    cur = {}
    for f in units:
        p = UNIT_FPEA_DIR + f.replace('/', '_') + '.json'
        if os.path.exists(p):
            mod = os.path.basename(f)[1:].replace('.o.bc', '')
            for fn, s in json.load(open(p))['entries'].items():
                cur[(fn, mod)] = sorted(s)
    return cur


def check_answer_key(ans, cur):
    """Print every answer-key item whose FPEA status/signals differ from the unit outputs."""
    for i, a in ans.items():
        k = (a['fn'], a['module'])
        if a['fpea_positive'] and (k not in cur or cur[k] != sorted(a['signals'])):
            print("MISMATCH pos", i, a, cur.get(k))
        if not a['fpea_positive'] and k in cur:
            print("MISMATCH neg", i, a, cur[k])


def main():
    ans = json.load(open(ANSWER_PATH))
    check_answer_key(ans, load_unit_signals())
    # population: corrected stratum weights from derive_results.py
    sp = json.load(open(STRATA_POP_PATH))
    W = sp['W_true']
    nF = sp['nF']
    tot = sp['tot_def']
    neg_pop = tot - nF
    # expert verdicts and the final label
    A = read_verdicts(RA_PATH)
    B = read_verdicts(RB_PATH)
    ids = sorted(A)
    adj = read_adjudication(ADJ_PATH)
    final = {i: (A[i] if A[i] == B[i] else adj[i]) for i in ids}
    pos = [i for i in ids if ans[i]['fpea_positive']]
    neg = [i for i in ids if not ans[i]['fpea_positive']]
    # per-stratum precision with Wilson CI, and the weighted precision
    by = defaultdict(lambda: [0, 0])
    for i in pos:
        by[st(ans[i]['signals'])][0 if final[i] == '1' else 1] += 1
    print("\n[Per-stratum precision + Wilson 95% CI]")
    num = var = 0
    for s, (tp, fp) in sorted(by.items()):
        n = tp + fp
        p = tp / n
        lo, hi = wilson(tp, n)
        num += W[s] * p
        var += W[s] ** 2 * p * (1 - p) / n
        print(f"  {s:7} n={n:3} prec={p:.3f} CI=[{lo:.3f},{hi:.3f}] w={W[s]:.4f}")
    wp = num + W['C2'] * 1.0
    se = math.sqrt(var)
    print(f"  Weighted precision (assuming C2=1) = {wp:.4f}  SE={se:.4f}"
          f"  95%CI≈[{wp-1.96*se:.4f},{wp+1.96*se:.4f}]")
    print(f"  (assuming C2 precision 0.95 = {num+W['C2']*0.95:.4f})")
    TPs = sum(final[i] == '1' for i in pos)
    simple_ci = tuple(round(x, 4) for x in wilson(TPs, len(pos)))
    print(f"  Simple precision = {TPs}/{len(pos)} = {TPs/len(pos):.4f} CI={simple_ci}")
    # recall (population-corrected)
    n1 = sum(final[i] == '1' for i in neg)
    nq = sum(final[i] == '?' for i in neg)
    n = len(neg)
    TP_pop = nF * wp
    print(f"\n[recall, population-corrected] FPEA={nF} negative population={neg_pop}"
          f" TP_pop≈{TP_pop:.0f}")
    for lab, k in (("confirmed FN(1) only", n1), ("incl. ?=FN", n1 + nq)):
        lo, hi = wilson(k, n)
        r_pt = TP_pop / (TP_pop + k / n * neg_pop)
        r_lo = TP_pop / (TP_pop + hi * neg_pop)
        r_hi = TP_pop / (TP_pop + lo * neg_pop)
        print(f"  {lab}: {k}/{n}  FN rate CI=[{lo:.4f},{hi:.4f}]"
              f"  recall point estimate={r_pt:.4f}  CI=[{r_lo:.4f},{r_hi:.4f}]")
    print(f"  rule-of-three (0/200): FN rate≤{3/n:.4f}"
          f" → recall≥{TP_pop/(TP_pop+3/n*neg_pop):.4f}")
    res = dict(W=W, wprec=wp, wprec_se=se, prec_simple=TPs / len(pos), TP_pop=TP_pop,
               neg_pop=neg_pop, n1=n1, nq=nq)
    with open('review_check.json', 'w') as out:
        json.dump(res, out, indent=1)


if __name__ == '__main__':
    main()

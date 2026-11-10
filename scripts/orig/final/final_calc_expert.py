"""Final computation from the expert round (rA/rB, audit v2.1) + the adjudicator's result
(adjudication_17_final.csv): Cohen's kappa, TP/FP, simple and stratum-weighted precision,
recall bounds on the 455-item reference set.
Run with cwd = $FIN (~/fpea_gt/final) by run_all.sh derive: `python3 final_calc_expert.py`.
Prints the result JSON and writes it to final_result_expert.json in the cwd."""
import csv
import json
from collections import Counter, defaultdict

ANSWER_PATH = '/home/user/rerun/fpea_pass/gt_answer_unit.json'
RA_PATH = '../expert_pkg/rA.csv'
RB_PATH = '../expert_pkg/rB.csv'
ADJ_PATH = '../expert_pkg/adjudication_17_final.csv'
# stratum population weights (rounded; C2 = 0.098 is added separately)
W = {'C1': 0.699, 'C4only': 0.128, 'C3': 0.068, 'C5': 0.010}


def read_verdicts(path):
    """Expert CSV -> {id: verdict}."""
    return {r['id']: r['verdict'] for r in csv.DictReader(open(path, encoding='utf-8-sig'))}


def read_adjudication(path):
    """Adjudication CSV -> {id: adjudicated verdict (adjudicated_verdict)}."""
    return {r['id']: r['adjudicated_verdict']
            for r in csv.DictReader(open(path, encoding='utf-8-sig'))}


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


def kappa(pairs):
    """Cohen's kappa and the observed agreement of a list of (A, B) verdict pairs."""
    n = len(pairs)
    cats = sorted({x for p in pairs for x in p})
    po = sum(1 for a, b in pairs if a == b) / n
    pe = sum((sum(1 for a, _ in pairs if a == c) / n) * (sum(1 for _, b in pairs if b == c) / n)
             for c in cats)
    return (po - pe) / (1 - pe), po


def main():
    ans = json.load(open(ANSWER_PATH))
    A = read_verdicts(RA_PATH)
    B = read_verdicts(RB_PATH)
    ids = sorted(A)
    adj = read_adjudication(ADJ_PATH)
    # final label: the common verdict, or the adjudicator's one when A and B disagree
    final = {i: (A[i] if A[i] == B[i] else adj[i]) for i in ids}
    pos = [i for i in ids if ans[i]['fpea_positive']]
    neg = [i for i in ids if not ans[i]['fpea_positive']]
    TP = sum(final[i] == '1' for i in pos)
    FP = sum(final[i] == '0' for i in pos)
    # per-stratum [TP, FP] counts and the weighted precision
    byst = defaultdict(lambda: [0, 0])
    for i in pos:
        if final[i] in '10':
            byst[st(ans[i]['signals'])][0 if final[i] == '1' else 1] += 1
    num = den = 0
    for s, (tp, fp) in byst.items():
        num += W[s] * tp / (tp + fp)
        den += W[s]
    n1 = sum(final[i] == '1' for i in neg)
    nq = sum(final[i] == '?' for i in neg)
    k, po = kappa([(A[i], B[i]) for i in ids])
    res = dict(kappa=k, agree=po, TP=TP, FP=FP, prec_simple=TP / (TP + FP),
               wprec_noC2=num / den, wprec_all=(num + 0.098) / (den + 0.098),
               recall_low=TP / (TP + n1 + nq),
               recall_high=TP / (TP + n1) if TP + n1 else 1.0,
               byst=dict(byst), neg_fn=n1, neg_q=nq,
               adj_dist=dict(Counter(adj.values())), final_dist=dict(Counter(final.values())))
    print(json.dumps(res, ensure_ascii=False, indent=1))
    with open('final_result_expert.json', 'w') as out:
        json.dump(res, out, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()

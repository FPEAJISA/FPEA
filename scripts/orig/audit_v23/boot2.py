#!/usr/bin/env python3
"""Recall estimators and the unit-level bootstrap of Section 5.2 / Supplementary S5 and S11.

Reads recon_pool2.json (the per-unit non-entry-point lists of the 500 stage-1 units), the
reference-set sample (gt_sample_unit.json) and the stratum constants, and computes for both
negative populations (pre-filter 112,856 = sensitivity only, post-filter 106,548 = paper):
  ratio estimator      FN = |N| * 15/200, recall = TP/(TP+FN)
  expansion estimator  FN_S = |pool|/200 * 15, FN_HT = 15,522/500 * FN_S
  Wilson interval of q = 15/200 mapped to recall
  unit bootstrap (B = 10,000, seed 517): units drawn with replacement, positives per stratum with
  replacement; variant with TP fixed (seed 518); design effect d = Var_boot(q)/Var_SRS(q).
Output boot2_results.json. Light: no bitcode needed. The earlier boot.py keyed the negative
sample's units by basename (10 collisions) and gave [0.868, 0.985], d 4.40."""
import collections
import json
import math
import os
import random
import statistics

from common import GT, OUTDIR, RESULTS, module_name, outpath, relunit, selected_units, units

N = {'C1': 90831, 'C4only': 16329, 'C3': 8874, 'C5': 1331}
n = {'C1': 80, 'C4only': 70, 'C3': 60, 'C5': 45}
TP = {'C1': 74, 'C4only': 63, 'C3': 50, 'C5': 31}
NC2 = 12602
NP = 129967
FN15 = {'dcn10_unblank_stream', 'dcn10_disable_plane', 'dcn10_prepare_bandwidth',
        'dcn10_set_cursor_attribute', 'dcn10_enable_stream_timing',
        'dcn10_enable_power_gating_plane', 'dcn10_dpp_pg_control', 'dcn10_hubp_pg_control',
        'gm107_therm_new', 'nvkm_i2c_bit_xfer', 'r100_pll_rreg', 'rvt_alloc_pd',
        'avc_remote_ctrl_work', 'vsc85xx_link_change_notify', 'rtl_8723e_c2h_command_handle'}
B = 10000


def prec_pt(tp):
    s = sum(N[h] * tp[h] / n[h] for h in N)
    return s / (NP - NC2), (s + NC2) / NP, s


def wilson(k, nn, z=1.96):
    p = k / nn
    d = 1 + z * z / nn
    c = (p + z * z / (2 * nn)) / d
    h = z * math.sqrt(p * (1 - p) / nn + z * z / (4 * nn * nn)) / d
    return c - h, c + h


def pct(a, p):
    a = sorted(a)
    return a[int(p * len(a))]


def main():
    src = os.environ.get('FPEA_RECON_POOL') or (
        f'{OUTDIR}/recon_pool2.json' if os.path.exists(f'{OUTDIR}/recon_pool2.json')
        else f'{RESULTS}/recon_pool2.json')
    rp = json.load(open(src))
    res = rp['pool']
    # the bootstrap draws from the stage-1 selection in its original (seed-913 shuffle) order;
    # the percentile results depend on this order
    sel = [relunit(u) for u in selected_units()]   # recon_pool2 keys are relative paths
    assert set(sel) == set(res), 'recon_pool2.json does not hold the seed-913 selection'
    units_all = units()
    pool_total = sum(len(v) for v in res.values())
    gt = json.load(open(GT))
    m = collections.Counter()
    fn = collections.Counter()
    for f, mb in gt['neg']:
        cands = [u for u, l in res.items() if module_name(u) == mb and f in l]
        if len(cands) != 1:
            raise SystemExit(f'negative sample item not mapped to exactly one unit: {f} {mb} {cands}')
        m[cands[0]] += 1
        if f in FN15:
            fn[cands[0]] += 1
    assert sum(m.values()) == 200 and sum(fn.values()) == 15, (sum(m.values()), sum(fn.values()))
    p_ex, p_in, TPh = prec_pt(TP)
    TPhat = TPh + NC2
    out = {}
    for label, N_neg in (('N_prefilter', 112856), ('N_clean', 106548)):
        FN_ratio = N_neg * 15 / 200
        rec_ratio = TPhat / (TPhat + FN_ratio)
        FN_S = (pool_total / 200) * 15
        FN_ht = (len(units_all) / 500) * FN_S
        rec_ht = TPhat / (TPhat + FN_ht)
        lo, hi = wilson(15, 200)
        random.seed(517)
        recs, qs, recs_ht = [], [], []
        for _ in range(B):
            su = [random.choice(sel) for _ in range(500)]
            mm = sum(m[u] for u in su)
            ff = sum(fn[u] for u in su)
            q = ff / mm if mm else 0.0
            pb = sum(len(res[u]) for u in su)
            tpb = {h: sum(1 for _ in range(n[h]) if random.random() < TP[h] / n[h]) for h in N}
            _, _, tph = prec_pt(tpb)
            tph += NC2
            recs.append(tph / (tph + N_neg * q))
            qs.append(q)
            recs_ht.append(tph / (tph + (len(units_all) / 500) * (pb / 200) * ff))
        random.seed(518)
        recs2 = []
        for _ in range(B):
            su = [random.choice(sel) for _ in range(500)]
            mm = sum(m[u] for u in su)
            ff = sum(fn[u] for u in su)
            q = ff / mm if mm else 0
            recs2.append(TPhat / (TPhat + N_neg * q))
        d = statistics.pvariance(qs) / (0.075 * 0.925 / 200)
        out[label] = dict(N_neg=N_neg, FN_ratio=FN_ratio, recall_ratio=rec_ratio, FN_S=FN_S,
                          FN_ht=FN_ht, recall_ht=rec_ht,
                          wilson_recall=[TPhat / (TPhat + N_neg * hi), TPhat / (TPhat + N_neg * lo)],
                          boot_recall=[pct(recs, .025), pct(recs, .975)],
                          boot_recall_negonly=[pct(recs2, .025), pct(recs2, .975)],
                          boot_recall_ht=[pct(recs_ht, .025), pct(recs_ht, .975)], deff=d)
        print(label, json.dumps(out[label]))
    out['pool_total'] = pool_total
    out['units'] = len(sel)
    out['zero_units'] = sum(1 for v in res.values() if not v)
    out['units_sampled'] = len(m)
    out['fn_by_unit'] = {os.path.basename(k): v for k, v in fn.items()}
    out['TPhat'] = TPhat
    out['prec_ex'] = p_ex
    out['prec_in'] = p_in
    dcn = [u for u in sel if module_name(u) == 'dcn10_hw_sequencer'][0]
    out['dcn10_expected'] = 200 * len(res[dcn]) / pool_total
    print('pool', pool_total, 'zero', out['zero_units'], 'sampled units', len(m), 'dcn10 E',
          out['dcn10_expected'])
    json.dump(out, open(outpath('boot2_results.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()

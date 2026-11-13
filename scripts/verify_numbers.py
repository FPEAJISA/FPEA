#!/usr/bin/env python3
"""Recompute every number quoted in the paper (each check is labelled with its section or table) from the
raw data (FPEA/UAFX outputs rf_*/rw_*, reference set, stored result json) and compare them.
Writes a markdown report (--out) and a json of the recomputed values (--json).
Usage: python3 verify_numbers.py [--heavy] [--out report.md] [--json values.json]
  --heavy: also the items that need IR re-interpretation (WL\\FPEA classification, iterator 726,
           ath12k, case-study IR) — parallel llvm-dis, several minutes."""
import argparse
import csv
import glob
import json
import math
import os
import random
import re
import sys
import subprocess
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from types import SimpleNamespace


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument('--heavy', action='store_true')
    ap.add_argument('--out', default=None)
    ap.add_argument('--json', default=None)
    return ap.parse_args()


# ---------------------------------------------------------------- paths (overridden by env.sh)
E = os.environ.get
# roots of the original measurement layout (env.sh: FPEA_HOME, FPEA_TMP; on the measurement
# server they were the home directory and /tmp)
HOME = E('FPEA_HOME') or os.path.expanduser('~')
TMP = E('FPEA_TMP', '/tmp')
SP = E('FPEA_SCRATCH') or E('FPEA_WORK') or f'{TMP}/scratchpad'
FIN = E('FPEA_RESULTS') or E('FPEA_FINAL', f'{HOME}/fpea_gt/final')
EXP = ((E('FPEA_DATA') + '/expert_pkg') if E('FPEA_DATA')
       else E('FPEA_EXPERT', f'{HOME}/fpea_gt/expert_pkg'))
PASSD = ((E('FPEA_DATA') + '/gt') if E('FPEA_DATA')
         else E('FPEA_PASS', f'{HOME}/rerun/fpea_pass'))
NOSAN = E('FPEA_RESULTS') or E('FPEA_NOSAN', f'{HOME}/rerun/nosan')
EPI = ((E('FPEA_DATA') + '/epi') if E('FPEA_DATA')
       else E('FPEA_EPI', f'{HOME}/epi_regfn'))
UNITS = E('FPEA_UNITS', f'{TMP}/units.txt')
UFPEA = E('FPEA_UFPEA', f'{TMP}/u_fpea')
LINKOUT = E('FPEA_LINKOUT', f'{TMP}/fpea_out')
LINKREP = (E('FPEA_RESULTS') + '/link_report_nosan14.txt') if E('FPEA_RESULTS') else None
LINKBC = E('FPEA_LINKBC', f'{HOME}/linux_bc/linked-nosan14-5.17.11')
DIS14 = E('FPEA_DIS14', '/usr/bin/llvm-dis-14')
DIS16 = E('FPEA_DIS16', f'{HOME}/llvm/build/bin/llvm-dis')
OUTD = E('FPEA_OUT')
RESD = E('FPEA_RESULTS')
SRC517 = E('FPEA_SRC14', f'{HOME}/rerun/nosan/src14/linux-5.17.11')
# link-layer analysis file list (artifact data/link/allfiles.txt)
ALLF = os.path.join(os.path.dirname(LINKOUT.rstrip('/')), 'allfiles.txt')
# Stored unit list and rf output used for the original sample draw (see check_sample_reproduction)
REPRO = E('FPEA_REPRO', os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UNITS_ORIG = E('FPEA_UNITS_ORIG', f'{REPRO}/data/fpea_out/list_5.17.11.txt')


def audit_result(name):
    """Result file of scripts/orig/audit_v23: the copy regenerated into out/ by the audit stage if
    present, else the stored copy in data/results (in both modes; until 2026-11-11 popN.json was
    read from FPEA_FINAL, where rerun mode never writes it)."""
    for d in (E('FPEA_OUTDIR', ''), RESD or '', f'{REPRO}/data/results'):
        if d and os.path.exists(f'{d}/{name}'):
            return json.load(open(f'{d}/{name}'))
    raise FileNotFoundError(name)
RF_ORIG = E('FPEA_RF_ORIG', f'{REPRO}/data/fpea_out/rf_5.17.11')
# re-run mode: items that cannot be reproduced, such as run times, are recorded as INFO only
RERUN = E('FPEA_MODE') == 'rerun'


def rf_dir(v):
    """Directory with the FPEA per-unit json files of version v."""
    return f'{OUTD}/rf_{v}' if OUTD else f'{SP}/rf_{v}'


def rw_dir(v):
    """Directory with the UAFX per-unit txt files of version v."""
    return f'{OUTD}/rw_{v}' if OUTD else f'{SP}/rw_{v}'


def list_path(v):
    """Unit list of version v."""
    if OUTD:
        return f'{OUTD}/list_{v}.txt'
    return UNITS if v == '5.17.11' else f'{SP}/list_{v}.txt'


def ph_path(v):
    """Placeholder scan result of version v."""
    return f'{RESD}/ph_{v}.txt' if RESD else f'{SP}/ph_{v}.txt'


def lit_path(name):
    """Named/literal struct scan result file."""
    if RESD:
        return f'{RESD}/{name}'
    return f'{SP}/{name}' if name.startswith('lit16_nosan16') else f'{FIN}/scripts/{name}'


def nproc():
    """Worker count of the heavy IR re-interpretation pools."""
    return int(os.environ.get("FPEA_NPROC", "14"))


# ---------------------------------------------------------------- constants
# version: (units, defined functions, FPEA, UAFX, FPEA∩UAFX, miss rate %); None = no UAFX run
EXPECTED_VERSIONS = {
    '5.17.11': (15522, 242823, 129967, 5899, 4912, 96.22),
    '5.19.17': (15913, 249502, 133213, 6011, 4983, 96.26),
    '6.9': (17579, 276117, 146481, 5527, 4416, 96.99),
    '7.1.4': (19649, 301306, 163919, 0, 0, None),
    '7.1.4-norand': (19649, 301291, 163919, 0, 0, None),
}
# handler names tracked across the header versions (Table 10)
HANDLER_NAMES = ['unlocked_ioctl', 'compat_ioctl', 'read', 'write', 'open', 'release', 'probe',
                 'remove', 'ndo_open', 'ndo_stop', 'ndo_start_xmit', 'suspend', 'resume',
                 'shutdown', 'ioctl', 'llseek', 'mmap']
HDR_VERSIONS = ('5.17', '5.19', '6.9', '7.1')
# iterator-type API names (fp_audit.py regex) for the heavy C3-only check
ITER_API_RE = re.compile(r'^(sort|sort_r|list_sort|bsearch|bus_for_each_\w+|driver_for_each_device'
                         r'|device_for_each_child\w*|class_for_each_device|idr_for_each|klist_\w+'
                         r'|\w+_for_each\w*|\w+_walk\w*|\w+_iterate\w*|iterate_\w+|walk_\w+)$')


# ---------------------------------------------------------------- reporting helpers
rows = []       # (section, item, expected, actual, status, note)
computed = {}   # 'section|item' -> recomputed value (written with --json)


def chk(sec, item, exp, act, tol=0, note=''):
    """Record one check: OK when the recomputed value equals the expected one (within tol)."""
    if isinstance(exp, (int, float)) and isinstance(act, (int, float)):
        ok = abs(exp - act) <= tol
    else:
        ok = (exp == act)
    rows.append((sec, item, exp, act, 'OK' if ok else 'MISMATCH', note))
    computed[f'{sec}|{item}'] = act
    return ok


def info(sec, item, act, note=''):
    """Record a value without a pass/fail verdict."""
    rows.append((sec, item, '', act, 'INFO', note))
    computed[f'{sec}|{item}'] = act


def chk_t(sec, item, exp, act, tol=0, note=''):
    """Timing measurement: a normal check, but INFO only in rerun mode."""
    if RERUN:
        return info(sec, item + f' (original measurement {exp})', act, note)
    return chk(sec, item, exp, act, tol, note)


def wilson(k, n, z=1.96):
    """Wilson score interval of k successes in n trials."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def r3(x):
    return round(x, 3)


# ---------------------------------------------------------------- data helpers
def stratum(sig):
    """Sampling stratum of a signal set: C3 > C5 > C4only (C4 without C1) > C1."""
    s = set(sig)
    if 'C3' in s:
        return 'C3'
    if 'C5' in s:
        return 'C5'
    if 'C4' in s and 'C1' not in s:
        return 'C4only'
    return 'C1'


def relkey(p):
    """Unit path relative to the drivers/ directory (tree-independent key)."""
    return p.split('/drivers/', 1)[1]


def module_name(f):
    """Module name of a unit path: drivers/x/.name.o.bc -> name."""
    return os.path.basename(f)[1:].replace('.o.bc', '')


def read_csv_by_id(path):
    return {r['id']: r for r in csv.DictReader(open(path, encoding='utf-8-sig'))}


def litcount(path, key):
    """Sum of the counts in a lit_*.txt file whose last column equals key."""
    tot = 0
    for l in open(path):
        p = l.split()
        if len(p) >= 2 and p[-1] == key:
            tot += int(p[-2])
    return tot


def dis14(bc):
    """Disassemble a typed-pointer (LLVM 14) bitcode unit to text."""
    return subprocess.run([DIS14, '-o', '-', bc], capture_output=True, text=True,
                          timeout=600).stdout


def dis16(bc):
    """Disassemble an opaque-pointer (LLVM 16) bitcode unit to text."""
    return subprocess.run([DIS16, '-o', '-', bc], capture_output=True, text=True).stdout


# ---------------------------------------------------------------- 1. FPEA/UAFX per version
def load_version(v):
    """Read rf_<v>/*.json and rw_<v>/*.txt of every unit listed for version v."""
    units = [l.strip() for l in open(list_path(v)) if l.strip()]
    n_fpea = n_defined = 0
    missing = 0
    fpea_set = set()
    uafx_set = set()
    kinds = Counter()
    uafx_nonempty = 0   # counted but not reported
    uafx_files = 0      # counted but not reported
    per_unit = {}
    for f in units:
        n = f.replace('/', '_')
        p = f'{rf_dir(v)}/{n}.json'
        if not os.path.exists(p):
            missing += 1
            continue
        d = json.load(open(p))
        n_fpea += len(d['entries'])
        n_defined += d['defined']
        per_unit[f] = d
        for fn in d['entries']:
            fpea_set.add((f, fn))
        w = f'{rw_dir(v)}/{n}.txt'
        if os.path.exists(w):
            uafx_files += 1
            lines = [l.strip() for l in open(w, errors='replace') if l.strip()]
            if lines:
                uafx_nonempty += 1
            for l in lines:
                q = l.split(':')
                if len(q) >= 2:
                    uafx_set.add((f, q[1]))
                    kinds[q[0]] += 1
    inter = len(uafx_set & fpea_set)
    return dict(units=len(units), missing=missing, FPEA=n_fpea, defined=n_defined,
                baseline=len(uafx_set), inter=inter,
                miss_rate=round((n_fpea - inter) / n_fpea * 100, 2) if n_fpea else None,
                kinds=dict(kinds), wl_minus_fpea=len(uafx_set) - inter,
                per_unit=per_unit, Wset=uafx_set, Fset=fpea_set)


def check_version_table():
    """5.1/5.4: per-version unit/function counts (Table 1) and the stored version_results.json.

    Returns the loaded per-version results (VR), used by most later checks."""
    VR = {}
    sec = '5.1/5.4 version table'
    for v, (u, dfn, fp, bl, it, mr) in EXPECTED_VERSIONS.items():
        r = load_version(v)
        VR[v] = r
        chk(sec, f'{v} units', u, r['units'])
        chk(sec, f'{v} defined functions', dfn, r['defined'])
        chk(sec, f'{v} FPEA', fp, r['FPEA'])
        chk(sec, f'{v} rf json missing', 0, r['missing'])
        if mr is not None:
            chk(sec, f'{v} UAFX', bl, r['baseline'])
            chk(sec, f'{v} FPEA∩UAFX', it, r['inter'])
            chk(sec, f'{v} miss rate', mr, r['miss_rate'], 0.005)
    stored = json.load(open(f'{FIN}/version_results.json'))
    for v in EXPECTED_VERSIONS:
        chk('version_results.json', f'{v} FPEA stored=recomputed', stored[v]['FPEA'],
            VR[v]['FPEA'])
    return VR


def check_first_measurement(VR):
    """5.1: rf_5.17.11 == $FPEA_TMP/u_fpea (first measurement) identical per unit."""
    item = 'units whose rf_5.17.11 vs u_fpea sets differ'
    if os.path.isdir(UFPEA):
        diff_units = 0
        for f, d in VR['5.17.11']['per_unit'].items():
            q = f'{UFPEA}/{f.replace("/", "_")}.json'
            if not os.path.exists(q) or set(json.load(open(q))['entries']) != set(d['entries']):
                diff_units += 1
        chk('5.1 input consistency', item, 0, diff_units)
    else:
        info('5.1 input consistency', item, 'skipped',
             note=f'first-measurement output {UFPEA} exists only on the measurement server — '
                  'on other machines this used to report OK without comparing; changed to INFO '
                  'on 2026-10-30')


def check_uafx_kinds(VR):
    """Table 7 / Abstract: UAFX kind counts per version and their 5.19→6.9 change."""
    k517, k519, k69 = VR['5.17.11']['kinds'], VR['5.19.17']['kinds'], VR['6.9']['kinds']
    expected_counts = {'READ_HDR': (984, 990, 609),
                       'WRITE_HDR': (891, 911, 560),
                       'MY_IOCTL': (489, 505, 345),
                       'IOCTL_CAND': (1388, 1415, 1469),
                       'INT_HANDLER_T': (2506, 2552, 2736),
                       'NETDEVIOCTL': (1, 1, 1)}
    for kind, e in expected_counts.items():
        chk('Table 7 UAFX kinds', f'{kind} 5.17/5.19/6.9', e,
            (k517.get(kind, 0), k519.get(kind, 0), k69.get(kind, 0)))

    def pct_change(kind):
        return round((k69[kind] - k519[kind]) / k519[kind] * 100)

    expected_change = {'READ_HDR': -38, 'WRITE_HDR': -39, 'MY_IOCTL': -32, 'IOCTL_CAND': 4,
                       'INT_HANDLER_T': 7}
    for kind, e in expected_change.items():
        chk('Table 7 UAFX kinds', f'{kind} 5.19→6.9 %', e, pct_change(kind))
    info('Abstract (1)', 'READ/WRITE/IOCTL decrease rate (5.19→6.9)',
         (pct_change('READ_HDR'), pct_change('WRITE_HDR'), pct_change('MY_IOCTL')),
         'compare with the abstract sentence "down 38%/37%/29% … INT_HANDLER_T up 9%" '
         '(Table 7 has −38/−39/−32/+7)')


def check_randstruct_control(VR):
    """5.3 / Ch. 4 / 5.4(2): WL∖FPEA and the RANDSTRUCT vs norand control of 7.1.4."""
    chk('5.3 WL∖FPEA', '5.17.11 WL∖FPEA', 987, VR['5.17.11']['wl_minus_fpea'])
    chk('Ch. 4', '7.1.4 RANDSTRUCT vs norand FPEA identical', True,
        VR['7.1.4']['FPEA'] == VR['7.1.4-norand']['FPEA'])
    # per-unit set identity (RANDSTRUCT vs norand): only the tree name in the path differs
    rand = {relkey(f): set(d['entries']) for f, d in VR['7.1.4']['per_unit'].items()}
    norand = {relkey(f): set(d['entries']) for f, d in VR['7.1.4-norand']['per_unit'].items()}
    common = set(rand) & set(norand)
    chk('5.4(2) RANDSTRUCT control', 'common units', 19649, len(common))
    chk('5.4(2) RANDSTRUCT control', 'units whose entry-point sets differ', 0,
        sum(1 for k in common if rand[k] != norand[k]))


# ---------------------------------------------------------------- 2. signals / strata
def check_strata(VR):
    """Table 2: stratum populations and weights of the 5.17.11 FPEA set (rf_5.17.11).

    Returns the population summary (strata, c2only, c3only_set, nF, totdef, W)."""
    per_unit = VR['5.17.11']['per_unit']
    strata = Counter()
    c2only = 0
    sigc = Counter()   # per-signal counts; not reported
    c1c4 = 0
    c3only = 0
    c3only_set = []
    for f, d in per_unit.items():
        for fn, s in d['entries'].items():
            ss = set(s)
            for x in ss:
                sigc[x] += 1
            if ss == {'C2'}:
                c2only += 1
                continue
            strata[stratum(ss)] += 1
            if 'C1' in ss and 'C4' in ss:
                c1c4 += 1
            if ss == {'C3'}:
                c3only += 1
                c3only_set.append((f, fn))
    nF = VR['5.17.11']['FPEA']
    totdef = VR['5.17.11']['defined']
    sp = json.load(open(f'{FIN}/strata_pop.json'))
    for k, e in {'C1': 90831, 'C4only': 16329, 'C3': 8874, 'C5': 1331}.items():
        chk('Table 2 stratum population', k, e, strata[k])
        chk('strata_pop.json', k, sp['strata'][k], strata[k])
    chk('Table 2 stratum population', 'C2 only', 12602, c2only)
    chk('Table 2 stratum population', 'nF', 129967, nF)
    chk('Table 2 stratum population', 'defined functions', 242823, totdef)
    W = {k: strata[k] / nF for k in strata}
    W['C2'] = c2only / nF
    for k, e in {'C1': 69.9, 'C2': 9.7, 'C3': 6.8, 'C4only': 12.6, 'C5': 1.0}.items():
        chk('Table 2 share %', k, e, round(W[k] * 100, 1))
    for k, e in {'C1': .6989, 'C4only': .1256, 'C3': .0683, 'C5': .0102, 'C2': .0970}.items():
        chk('Table 2 weight W', k, e, round(W[k], 4))
    chk('Table 2 auxiliary', 'C1∩C4', 161, c1c4)
    chk('Table 2 auxiliary', 'C3 only', 8798, c3only)
    chk('5.10', 'FPEA/defined functions %', 53.5, round(nF / totdef * 100, 1))
    c2only_in_uafx = sum(
        1 for (f, fn) in VR['5.17.11']['Wset']
        if fn in per_unit.get(f, {}).get('entries', {})
        and set(per_unit[f]['entries'][fn]) == {'C2'})
    chk('Ch. 1', 'C2-only 12,602 have 0 in UAFX', 0, c2only_in_uafx)
    return SimpleNamespace(strata=strata, c2only=c2only, c3only_set=c3only_set, nF=nF,
                           totdef=totdef, W=W)


# ---------------------------------------------------------------- 3. reference set
def load_reference_set():
    """Load the answer key, the two reviewers' verdicts (rA/rB) and the adjudication files."""
    ref = SimpleNamespace()
    ref.ans = json.load(open(f'{PASSD}/gt_answer_unit.json'))
    ref.RA = read_csv_by_id(f'{EXP}/rA.csv')
    ref.RB = read_csv_by_id(f'{EXP}/rB.csv')
    ref.ids = sorted(ref.RA)
    ref.ADJF = read_csv_by_id(f'{EXP}/adjudication_17_final.csv')
    ref.ADJR = read_csv_by_id(f'{EXP}/adjudication_17_reply.csv')
    ref.ADJ0 = read_csv_by_id(f'{EXP}/adjudication_17.csv')
    return ref


def check_reference_set(VR, ref):
    """Table 3: size and composition of the reference set; answer key vs current FPEA output."""
    ans, RA, RB, ids = ref.ans, ref.RA, ref.RB, ref.ids
    per_unit = VR['5.17.11']['per_unit']
    chk('Table 3', 'reference set n', 455, len(ids))
    chk('Table 3', 'rA/rB ids identical', True, set(RA) == set(RB) == set(ans))
    ref.pos = [i for i in ids if ans[i]['fpea_positive']]
    ref.neg = [i for i in ids if not ans[i]['fpea_positive']]
    pos, neg = ref.pos, ref.neg
    chk('Table 3', 'positives', 255, len(pos))
    chk('Table 3', 'negatives', 200, len(neg))
    chk('Table 3', 'positive stratum composition', {'C1': 80, 'C4only': 70, 'C3': 60, 'C5': 45},
        dict(Counter(stratum(ans[i]['signals']) for i in pos)))
    # answer key == current FPEA output?
    cur = {}
    for f, d in per_unit.items():
        mod = module_name(f)
        for fn, s in d['entries'].items():
            cur.setdefault((fn, mod), sorted(s))
    mm = (sum(1 for i in pos
              if cur.get((ans[i]['fn'], ans[i]['module'])) != sorted(ans[i]['signals']))
          + sum(1 for i in neg if (ans[i]['fn'], ans[i]['module']) in cur))
    chk('Table 3', 'answer key vs current FPEA output mismatches (signals; same-named units pass '
        'if either matches)', 0, mm)
    dupmod = Counter(module_name(f) for f in per_unit)
    spanning = [i for i in ids
                if dupmod[ans[i]['module']] > 1
                and sum(1 for f in per_unit
                        if module_name(f) == ans[i]['module']
                        and ans[i]['fn'] in per_unit[f]['entries']) > 1]
    chk('Table 3', 'answer-key (function, module) pairs spanning two units', ['G128'], spanning,
        note='if_usb (libertas/libertas_tf) same-named units; the verdict unit is fixed by '
             'unit_map_internal.json')


def check_labels_and_agreement(ref):
    """Table 3 / 5.2: final labels, adjudication of the 1↔0 conflicts, agreement rate and κ."""
    ids, RA, RB = ref.ids, ref.RA, ref.RB
    ADJF, ADJR, ADJ0 = ref.ADJF, ref.ADJR, ref.ADJ0
    ref.final = {i: (RA[i]['verdict'] if RA[i]['verdict'] == RB[i]['verdict'] else ADJF[i]['adjudicated_verdict'])
                 for i in ids}
    ref.frule = {i: (RA[i]['rule'] if RA[i]['verdict'] == RB[i]['verdict']
                     else ADJF[i]['adjudicated_rule'])
                 for i in ids}
    final = ref.final
    chk('Table 3', 'final label distribution', {'1': 218, '0': 222, '?': 15},
        dict(Counter(final.values())))
    conf = [i for i in ids if {RA[i]['verdict'], RB[i]['verdict']} == {'1', '0'}]
    chk('Table 3', '1↔0 conflicts', 17, len(conf))
    chk('Table 3', 'adjudication outcome 1/0', {'1': 6, '0': 11},
        dict(Counter(ADJF[i]['adjudicated_verdict'] for i in conf)))
    chk('Table 3', 'adjudication file ids = conflict ids', True,
        set(ADJF) == set(conf) == set(ADJR) == set(ADJ0))
    chk('5.2', 'changes after discussion (revised column)', 5,
        sum(1 for i in ADJF if ADJF[i]['revised'].strip()))
    chk('5.2', 'verdicts changed vs first reply (4) + reason-only replacement (1) = 5', (4, 5),
        (sum(1 for i in ADJF if ADJF[i]['adjudicated_verdict'] != ADJR[i]['adjudicated_verdict']),
         sum(1 for i in ADJF if ADJF[i]['revised'].strip())),
        note='G034·G317→1, G315·G046→0, G136 reason replaced')
    final_r = {i: (RA[i]['verdict'] if RA[i]['verdict'] == RB[i]['verdict'] else ADJR[i]['adjudicated_verdict'])
               for i in ids}
    chk('5.2', 'TP before correction (first reply)', 218, sum(final_r[i] == '1' for i in ref.pos))
    # Cohen's κ of the two reviewers
    n = len(ids)
    pairs = [(RA[i]['verdict'], RB[i]['verdict']) for i in ids]
    po = sum(a == b for a, b in pairs) / n
    cats = sorted({x for p in pairs for x in p})
    pe = sum((sum(a == c for a, _ in pairs) / n) * (sum(b == c for _, b in pairs) / n)
             for c in cats)
    kappa = (po - pe) / (1 - pe)
    chk('Table 3', 'agreement rate', 0.963, round(po, 3))
    chk('Table 3', 'κ', 0.930, round(kappa, 3))


def check_precision(ref, pop):
    """Table 4: TP/FP per stratum, simple and weighted precision with confidence intervals."""
    ans, pos, final, W = ref.ans, ref.pos, ref.final, pop.W
    TP = sum(final[i] == '1' for i in pos)
    FP = sum(final[i] == '0' for i in pos)
    chk('Table 4', 'TP', 218, TP)
    chk('Table 4', 'FP', 37, FP)
    by = defaultdict(lambda: [0, 0])
    for i in pos:
        by[stratum(ans[i]['signals'])][0 if final[i] == '1' else 1] += 1
    # stratum: (TP, FP, precision, CI low, CI high)
    exp_by = {'C1': (74, 6, .925, .846, .965),
              'C4only': (63, 7, .900, .808, .951),
              'C3': (50, 10, .833, .720, .907),
              'C5': (31, 14, .689, .543, .805)}
    num = var = 0
    for s, (tp, fp, p, lo, hi) in exp_by.items():
        t, f_ = by[s]
        nn = t + f_
        pp = t / nn
        wl = wilson(t, nn)
        chk('Table 4', f'{s} TP/FP', (tp, fp), (t, f_))
        chk('Table 4', f'{s} precision', p, r3(pp))
        chk('Table 4', f'{s} CI', (lo, hi), (r3(wl[0]), r3(wl[1])))
        num += W[s] * pp
        # stratified variance with the unbiased stratum variance p(1-p)/(n-1) (v2.1+ of the paper;
        # the 10/23 draft used /n: SE 0.021, CI (0.879, 0.962))
        var += W[s] ** 2 * pp * (1 - pp) / (nn - 1)
    wp = num + W['C2'] * 1.0          # including C2 (precision 1 assumed)
    se = math.sqrt(var)
    w4 = sum(W[s] for s in exp_by)    # weight mass of the four sampled strata
    wp_ex = num / w4                   # four strata renormalised = headline "measured" value
    se_ex = se / w4
    chk('Table 4', 'simple precision', 0.855, r3(TP / (TP + FP)))
    chk('Table 4', 'simple precision CI', (0.806, 0.893),
        tuple(r3(x) for x in wilson(TP, TP + FP)))
    chk('Table 4', 'weighted precision excl. C2 (measured, headline)', 0.912, r3(wp_ex),
        note=f'exact value {wp_ex:.5f}; four strata, W renormalised by {w4:.4f}')
    chk('Table 4', 'weighted SE excl. C2 (n-1)', 0.0238, round(se_ex, 4))
    chk('Table 4', 'weighted CI excl. C2', (0.865, 0.959),
        (r3(wp_ex - 1.96 * se_ex), r3(wp_ex + 1.96 * se_ex)))
    chk('Table 4', 'weighted precision incl. C2 (W_true)', 0.920, r3(wp),
        note=f'exact value {wp:.5f}; with 3-digit rounded weights (0.699/0.128/0.068/0.010/0.098) '
             'it is 0.9206→0.921. The text uses 0.920 (W_true) for population estimates')
    chk('Table 4', 'weighted SE incl. C2 (n-1)', 0.0215, round(se, 4))
    chk('Table 4', 'weighted CI incl. C2', (0.878, 0.963), (r3(wp - 1.96 * se), r3(wp + 1.96 * se)))
    chk('5.2', 'over-approximation rate 1 - precision incl. C2 (%)', 8.0, round((1 - wp) * 100, 1))
    ref.TP, ref.FP, ref.wp, ref.wp_ex = TP, FP, wp, wp_ex


def check_recall(ref, pop):
    """5.2: negatives, population extrapolation, recall and its CI, the 15 '?' items."""
    RA, RB, pos, neg, final = ref.RA, ref.RB, ref.pos, ref.neg, ref.final
    TP, wp, nF, totdef = ref.TP, ref.wp, pop.nF, pop.totdef
    n1 = sum(final[i] == '1' for i in neg)
    nq = sum(final[i] == '?' for i in neg)
    chk('5.2', 'negatives confirmed FN', 0, n1)
    chk('5.2', 'negatives ?', 15, nq)
    # |N| = defined functions after the Section 3.4 filter (popN.json, llvm-dis define minus the
    # name filter) minus the FPEA entry points. The pre-filter value totdef - nF = 112,856 is the
    # sensitivity figure of Section 5.10 (recall 0.934).
    neg_pop_pre = totdef - nF
    popn = audit_result('popN.json')['totals']
    chk('5.1', 'defined functions after the 3.4 filter', 236515, popn['define_clean'])
    chk('5.1', 'defined functions before the filter (llvm-dis = fpea json)', (242823, 242823),
        (popn['define_all'], popn['json_defined']))
    chk('Appendix D / S11', 'filter removes (header inline copies)', 6308,
        popn['define_all'] - popn['define_clean'])
    neg_pop = popn['define_clean'] - nF
    chk('5.2', 'negative population |N| (post-filter)', 106548, neg_pop)
    chk('5.2', '|N| = popN N_clean', popn['N_clean'], neg_pop)
    chk('5.10', 'pre-filter negative population (sensitivity)', 112856, neg_pop_pre)
    TP_pop = nF * wp
    FN_pop = neg_pop * nq / 200
    chk('5.2', 'TP_pop', 119629, round(TP_pop))
    chk('5.2', 'FN_pop (ratio estimator)', 7991, round(FN_pop))
    rec = TP_pop / (TP_pop + FN_pop)
    lo, hi = wilson(nq, 200)
    chk('5.2', 'recall (ratio estimator, primary)', 0.937, r3(rec))
    chk('5.2', 'recall Wilson CI (SRS assumption)', (0.903, 0.961),
        (r3(TP_pop / (TP_pop + hi * neg_pop)), r3(TP_pop / (TP_pop + lo * neg_pop))))
    FN_pre = neg_pop_pre * nq / 200
    chk('5.10', 'pre-filter FN / recall (sensitivity)', (8464, 0.934),
        (round(FN_pre), r3(TP_pop / (TP_pop + FN_pre))))
    chk('5.10', 'pre-filter FN inflation %', 6, round((FN_pre / FN_pop - 1) * 100))
    info('5.2 alternative', 'recall (direct sum of sample counts)', r3(TP / (TP + n1 + nq)))
    info('5.2 alternative', 'rule-of-three recall lower bound',
         r3(TP_pop / (TP_pop + 3 / 200 * neg_pop)))
    info('5.2 alternative', '?=0 recall CI',
         (r3(TP_pop / (TP_pop + wilson(0, 200)[1] * neg_pop)), 1.0))
    qids = [i for i in neg if final[i] == '?']
    chk('5.2 ?15', 'all 15 have A=B=? and rule other-file', True,
        all(RA[i]['verdict'] == RB[i]['verdict'] == '?'
            and RA[i]['rule'] == RB[i]['rule'] == 'other-file' for i in qids))
    chk('5.2 ?15', 'no ? in positive sample', 0, sum(final[i] == '?' for i in pos))
    ref.qids = qids


def check_fp_types(ref):
    """Table 5: false-positive types (adjudicated rule) per stratum; fp_types.json."""
    ans, RA, RB, ADJF, pos, final = ref.ans, ref.RA, ref.RB, ref.ADJF, ref.pos, ref.final
    fpids = [i for i in pos if final[i] == '0']

    def fp_rule(i):
        if RA[i]['verdict'] != RB[i]['verdict']:
            return ADJF[i]['adjudicated_rule']
        a, b = RA[i]['rule'], RB[i]['rule']
        return a if a == b else '/'.join(sorted([a, b]))

    fr = Counter(fp_rule(i) for i in fpids)
    chk('Table 5', 'FP types', {'internal-dispatch': 27, 'sync-callback': 7, 'internal-dispatch/sync-callback': 3}, dict(fr))
    fxs = defaultdict(Counter)
    for i in fpids:
        fxs[fp_rule(i)][stratum(ans[i]['signals'])] += 1
    chk('Table 5', 'internal-dispatch per stratum', {'C1': 6, 'C4only': 6, 'C3': 2, 'C5': 13},
        dict(fxs['internal-dispatch']))
    chk('Table 5', 'sync-callback per stratum', {'C3': 7}, dict(fxs['sync-callback']))
    chk('Table 5', 'mixed per stratum', {'C4only': 1, 'C3': 1, 'C5': 1},
        dict(fxs['internal-dispatch/sync-callback']))
    chk('Table 5', 'FP per-stratum total', {'C1': 6, 'C4only': 7, 'C3': 10, 'C5': 14},
        dict(Counter(stratum(ans[i]['signals']) for i in fpids)))
    chk('Table 5/D3', 'G162 final rule (adjudicated)', 'internal-dispatch', ref.frule['G162'])
    chk('Table 5/D3', 'G162 B rule', 'sync-callback', RB['G162']['rule'])
    ft = json.load(open(f'{FIN}/fp_types.json'))
    chk('fp_types.json', 'fp_ids = recomputed', sorted(fpids), sorted(ft['fp_ids']))
    ref.fpids = fpids


def check_rule_distributions(ref):
    """Table 3: rule distribution of reviewer A, reviewer B and of the true positives."""
    ids, RA, RB, ADJF, pos, final = ref.ids, ref.RA, ref.RB, ref.ADJF, ref.pos, ref.final
    chk('Table 3', 'A rule distribution',
        {'internal-helper': 153, 'exported-service': 35, 'deferred': 43, 'op-table': 142, 'internal-dispatch': 17,
         'probe-remove': 15, 'teardown': 6, 'irq': 18, 'other-file': 15, 'sync-callback': 10, 'comparison': 1},
        dict(Counter(RA[i]['rule'] for i in ids)))
    chk('Table 3', 'B rule distribution',
        {'internal-helper': 150, 'exported-service': 35, 'deferred': 47, 'op-table': 129, 'internal-dispatch': 30,
         'probe-remove': 17, 'teardown': 8, 'irq': 16, 'other-file': 15, 'sync-callback': 8},
        dict(Counter(RB[i]['rule'] for i in ids)))
    tpr = Counter()
    for i in pos:
        if final[i] != '1':
            continue
        if RA[i]['verdict'] != RB[i]['verdict']:
            tpr[ADJF[i]['adjudicated_rule']] += 1
            continue
        a, b = RA[i]['rule'], RB[i]['rule']
        tpr[a if a == b else 'mixed'] += 1
    chk('Table 3', 'TP rules',
        {'op-table': 125, 'deferred': 40, 'irq': 15, 'probe-remove': 13, 'teardown': 7,
         'mixed': 18},
        dict(tpr))


def original_unit(f, per_unit):
    """The stored original rf_5.17.11 json of unit f when present, else the current output."""
    p = f'{RF_ORIG}/{f.replace("/", "_")}.json'
    if os.path.isdir(RF_ORIG) and os.path.exists(p):
        return json.load(open(p))
    return per_unit.get(f)


def check_sample_reproduction(VR, ref):
    """Appendix D: re-draw the positive sample (seed 517) and compare with the answer key.

    Only the positive part of sample_gt_unit.py is deterministic, so only that set is reproduced.
    The sample depends on the order of the unit list. The list used for the original draw (find
    output order = filesystem order on the measurement server) is stored in the artifact at
    data/fpea_out/list_5.17.11.txt, and since run-fpea in rerun builds a sorted list (found in the
    2026-10-27 new-machine reproduction), this check alone runs in the stored original list
    order. setup.py layout restores the paths to match the measurement server, so they match the
    per_unit keys as they are.
    Also, fpea's json is emitted from std::map<Function*, …> (pointer order), so the function
    order within a unit changes from run to run (the set is the same; in the 2026-10-27
    new-machine reproduction 4,341 of 10,063 units differed only in order). random.sample depends
    on that order, so this check runs on the stored output used for the original draw
    (data/fpea_out/rf_5.17.11)."""
    ans, pos, neg = ref.ans, ref.pos, ref.neg
    per_unit = VR['5.17.11']['per_unit']
    unit_list = UNITS_ORIG if os.path.exists(UNITS_ORIG) else UNITS
    posall = []
    for f in [l.strip() for l in open(unit_list)]:
        d = original_unit(f, per_unit)
        if not d:
            continue
        mod = module_name(f)
        for fn, s in d['entries'].items():
            if set(s) == {'C2'}:
                continue
            posall.append((fn, mod, tuple(sorted(s))))
    byp = defaultdict(list)
    for fn, mod, sig in posall:
        byp[stratum(sig)].append((fn, mod, sig))
    random.seed(517)
    samp = []
    for k, q in {'C1': 80, 'C4only': 70, 'C3': 60, 'C5': 45}.items():
        samp += random.sample(byp[k], min(q, len(byp[k])))
    seen = set()
    posU = []
    for fn, mod, sig in samp:
        if fn in seen:
            continue
        seen.add(fn)
        posU.append((fn, mod))
    chk('Appendix D / S11', 'duplicate-name drop never triggered (quota 255 = final 255)',
        (255, 255), (len(samp), len(posU)))
    namecount = Counter(fn for fn, mod, sig in posall)
    chk('Appendix D / S11', 'positives with a same-name entry point in another unit', 11,
        sum(1 for fn, mod in posU if namecount[fn] > 1))
    gt_pos = {(ans[i]['fn'], ans[i]['module']) for i in pos}
    unit_order = "stored original list" if unit_list == UNITS_ORIG else "current list"
    fn_order = "stored original output" if os.path.isdir(RF_ORIG) else "current output"
    chk('Appendix D sample reproduction', 'positives 255 (seed 517) reproduced', True,
        set(posU) == gt_pos and len(posU) == 255,
        note=f'unit order = {unit_order}, function order = {fn_order}; the 200 negatives depend '
             'on Pool order (imap_unordered) and cannot be reproduced from the seed alone → kept '
             'in gt_sample_unit.json')
    gs = json.load(open(f'{PASSD}/gt_sample_unit.json'))
    chk('Appendix D sample reproduction', 'gt_sample_unit.json negatives = answer-key negatives',
        True, {(a, b) for a, b in gs['neg']} == {(ans[i]['fn'], ans[i]['module']) for i in neg})


# ---------------------------------------------------------------- 4. link layer: the 15 ? items
def check_link_layer_q15(ref):
    """5.9(a) / Appendix H: the 15 '?' negatives are found in the link-layer output."""
    ans, qids = ref.ans, ref.qids
    q15 = json.load(open(f'{FIN}/link_layer_q15.json'))
    chk('5.9(a)', 'link_layer_q15 id = ? 15', sorted(qids), sorted(q15))
    # look up directly in the link-layer output
    link_fn = defaultdict(set)
    for jf in os.listdir(LINKOUT):
        for fn, s in json.load(open(f'{LINKOUT}/{jf}'))['entries'].items():
            link_fn[fn] |= set(s)
    sigs = Counter()
    for i in qids:
        s = link_fn.get(ans[i]['fn'], set())
        sigs['C1' if 'C1' in s else ('C4' if 'C4' in s else ('other' if s else 'none'))] += 1
    chk('5.9(a)', 'identified 15/15 in the link layer, C1 13 / C4 2', {'C1': 13, 'C4': 2},
        dict(sigs))
    chk('Appendix H', 'dcn10_init.c registration count', 8,
        sum('dcn10_init.c' in q15[i]['unit_reg_loc'] for i in qids))


# ---------------------------------------------------------------- 5. typed vs opaque
def check_typed_vs_opaque(VR):
    """Table 12: rf_5.17.11 (typed pointers, LLVM 14) vs fpea16tree (opaque pointers, LLVM 16)."""
    L16 = [l.strip() for l in open(list_path('nosan16')) if l.strip()]
    F16 = {}
    for f in L16:
        n = f.replace("/", "_")
        p = f'{OUTD}/rf_nosan16/{n}.json' if OUTD else f'{SP}/fpea16tree/{n}.json'
        if os.path.exists(p):
            F16[relkey(f)] = set(json.load(open(p))['entries'])
    F14 = {}
    for f, d in VR['5.17.11']['per_unit'].items():
        if '/drivers/' not in f:
            continue
        k = relkey(f)
        k = k.rsplit('/', 1)[0] + '/' + k.rsplit('/', 1)[1][1:]   # .name.o.bc → name.o.bc
        F14[k] = set(d['entries'])
    com = set(F14) & set(F16)
    chk('Table 12', 'units 14/16', (15522, 15452), (VR['5.17.11']['units'], len(F16)))
    chk('Table 12', 'common units', 15451, len(com))
    chk('Table 12', 'FPEA common typed/opaque', (128571, 128541),
        (sum(len(F14[k]) for k in com), sum(len(F16[k]) for k in com)))
    chk('Table 12', 'differing units / symmetric difference', (8, 30),
        (sum(1 for k in com if F14[k] != F16[k]), sum(len(F14[k] ^ F16[k]) for k in com)))
    chk('Table 12', 'functions only in opaque', 0, sum(len(F16[k] - F14[k]) for k in com))
    chk('Table 12', 'FPEA total opaque', 128544, sum(len(v) for v in F16.values()))
    h16 = json.load(open(f'{NOSAN}/hitfull_5.17.11-llvm16.json'))
    chk('Table 12', 'opaque simple hit rate', (43.81, 3879, 8855),
        (h16['rate'], h16['hit'], h16['designated']))


# ---------------------------------------------------------------- 6. hit rate / semantic hit rate
def check_hit_rates():
    """Table 11: internal consistency of the stored hitfull_*.json / semantic_hit_*.json."""
    # version: (designated, hit, rate %)
    simple = {'5.17.11': (8807, 3862, 43.85),
              '5.19.17': (8964, 3944, 44.00),
              '6.9': (5914, 2455, 41.51),
              '7.1.4-norand': (11136, 5919, 53.15),
              '7.1.4': (11136, 6127, 55.02)}
    for v, (dd, dh, rate) in simple.items():
        h = json.load(open(f'{NOSAN}/hitfull_{v}.json'))
        s = json.load(open(f'{FIN}/semantic_hit_{v}.json'))
        chk('Table 11 simple hit rate', v, (dd, dh, rate), (h['designated'], h['hit'], h['rate']))
        chk('Table 11 semantic file agreement', v, (dd, dh), (s['designated'], s['has_fn']))
        chk('Table 11 simple hit rate formula', v, rate, round(dh / dd * 100, 2))
    # version: (with_header, index_same, semantic_hit, rate %, wrong_field_fn, intended_missed)
    semantic = {'5.17.11': (7060, 7060, 3290, 46.60, 0, 0),
                '5.19.17': (7183, 7147, 3341, 46.51, 23, 4),
                '6.9': (4055, 2922, 1724, 42.52, 93, 100),
                '7.1.4-norand': (9185, 3163, 532, 5.79, 4732, 3748)}
    for v, (wh, same, sem, rate, wrong, missed) in semantic.items():
        s = json.load(open(f'{FIN}/semantic_hit_{v}.json'))
        chk('Table 11 semantic hit rate', v, (wh, same, sem, rate, wrong, missed),
            (s['with_header'], s['index_same'], s['semantic_hit'],
             s['rate_semantic_within_header'], s.get('wrong_field_fn', 0),
             s.get('intended_missed', 0)))
        chk('Table 11 semantic hit rate formula', v, rate, round(sem / wh * 100, 2))
    chk('Table 11', '6.9 index-shifted slots', 1133,
        json.load(open(f'{FIN}/semantic_hit_6.9.json'))['index_moved'])


# ---------------------------------------------------------------- 7. named/literal, placeholder
def check_named_literal():
    """Table 9: named vs literal struct counts (lit_*.txt) per version and LLVM build."""
    # version: (named fops, LITERAL_FOPS, platform_driver, pci_driver, device_attribute, ndo)
    expected = {'5.17.11': (2102, 12, 2852, 710, 4699, 386),
                '5.19.17': (2140, 12, 2973, 713, 4781, 391),
                '6.9': (1102, 1347, 3464, 717, 5176, 381)}
    for v, (named, lit, pd, pci, da, ndo) in expected.items():
        P = lit_path(f'lit_{v}.txt')
        chk('Table 9 named/literal', f'{v} file_operations/LITERAL', (named, lit),
            (litcount(P, '%struct.file_operations'), litcount(P, 'LITERAL_FOPS')))
        chk('Table 9 named/literal', f'{v} platform/pci/device_attribute/net_device_ops',
            (pd, pci, da, ndo),
            tuple(litcount(P, '%struct.' + k)
                  for k in ('platform_driver', 'pci_driver', 'device_attribute',
                            'net_device_ops')))
    chk('Table 9', '6.9 literal share %', 55, round(1347 / (1102 + 1347) * 100))
    chk('Table 9', '5.17.11 LLVM16 named', 2114,
        litcount(lit_path('lit16_nosan16-5.17.11.txt'), '%struct.file_operations'))
    chk('Table 9', '7.1.4 norand named / strict literal pattern', (2800, 21),
        (litcount(lit_path('lit16_7.1.4-norand.txt'), '%struct.file_operations'),
         litcount(lit_path('lit16_7.1.4-norand.txt'), 'LITERAL_FOPS')))
    chk('Table 9', '7.1.4 RANDSTRUCT named / strict literal pattern', (2800, 21),
        (litcount(lit_path('lit16s_7.1.4.txt'), '%struct.file_operations'),
         litcount(lit_path('lit16s_7.1.4.txt'), 'LITERAL_FOPS')))


def check_placeholder_units():
    """Table 9: units with placeholder struct types (ph_*.txt)."""
    for v, (ph, tot) in {'5.17.11': (28, 15522), '5.19.17': (28, 15913),
                         '6.9': (11451, 17579)}.items():
        ls = open(ph_path(v)).read().split('\n')
        chk('Table 9 placeholder units', v, (ph, tot),
            (sum(l.endswith('PLACEHOLDER') for l in ls),
             sum(l.endswith(('PLACEHOLDER', 'CLEAN')) for l in ls)))


def check_kind_drift():
    """Table 8: causes of the UAFX kind losses 5.19→6.9 (kind_drift_519_69.json)."""
    kd = json.load(open(f'{FIN}/kind_drift_519_69.json'))
    # kind: (lost, A_not_defined, B_no_initializer, C_index_shift, D_rule_index_ok, E_struct…)
    expected = {'READ_HDR': (369, 10, 356, 3, 0, 0),
                'WRITE_HDR': (356, 22, 331, 3, 0, 0),
                'MY_IOCTL': (150, 8, 138, 3, 0, 1),
                'INT_HANDLER_T': (38, 29, 5, 0, 0, 4)}

    def cause(kind, t):
        return kd['cause'].get(f'{kind}|{t}', 0)

    for kind, (lost, a, b, c, d, e) in expected.items():
        act = (kd['lost'][kind], cause(kind, 'A_not_defined'), cause(kind, 'B_no_initializer'),
               cause(kind, 'C_index_shift'), cause(kind, 'D_rule_index_ok'),
               cause(kind, 'E_struct_not_in_rule'))
        chk('Table 8 kind_drift', kind, (lost, a, b, c, d, e), act)
        chk('Table 8 kind_drift sum', kind, lost, sum(act[1:]))


# ---------------------------------------------------------------- 8. header offsets
def check_header_offsets():
    """Table 10 / 5.4(3): handler field indices across the four header versions."""
    H = json.load(open(f'{EPI}/handler_offset.json'))
    tracked = moved = m69 = m71 = m69any = 0
    for st, per in H.items():
        if not all(per[v] for v in per):
            continue
        for h in HANDLER_NAMES:
            index = {v: (per[v].index(h) if h in per[v] else None) for v in per}
            vals = [index[v] for v in HDR_VERSIONS]
            if any(x is None for x in vals):
                continue
            tracked += 1
            if len(set(vals)) > 1:
                moved += 1
            if vals[0] != vals[2]:
                m69 += 1
            if len(set(vals[:3])) > 1:
                m69any += 1
            if vals[0] != vals[3]:
                m71 += 1
    chk('Table 10/①③', 'struct count / handler name count', (20, 17),
        (len(H), len(HANDLER_NAMES)))
    chk('Table 10/①③', 'tracked 59 / moved 23', (59, 23), (tracked, moved))
    chk('Table 10/①③', 'moved share %', 39, round(moved / tracked * 100))
    chk('5.4(3) footnote',
        'moved within the three versions 5.17·5.19·6.9 / direct 5.17 vs 7.1 comparison',
        (19, 15), (m69any, m71))
    info('5.4(3) footnote', '5.17 vs 6.9 direct comparison (reference)', m69,
         'the 19 in the footnote counts handlers that differ at least once across the three '
         'versions')

    def idx(st, h):
        return tuple(H[st][v].index(h) if h in H[st][v] else None for v in HDR_VERSIONS)

    # (struct, handler, index in 5.17/5.19/6.9/7.1)
    expected_index = [
        ('file_operations', 'llseek', (1, 1, 1, 2)),
        ('file_operations', 'read', (2, 2, 2, 3)),
        ('file_operations', 'write', (3, 3, 3, 4)),
        ('file_operations', 'unlocked_ioctl', (10, 10, 9, 10)),
        ('file_operations', 'compat_ioctl', (11, 11, 10, 11)),
        ('file_operations', 'mmap', (12, 12, 11, 12)),
        ('file_operations', 'open', (14, 14, 13, 13)),
        ('file_operations', 'release', (16, 16, 15, 15)),
        ('pci_driver', 'probe', (3, 3, 2, 2)),
        ('pci_driver', 'remove', (4, 4, 3, 3)),
        ('pci_driver', 'suspend', (5, 5, 4, 4)),
        ('pci_driver', 'resume', (6, 6, 5, 5)),
        ('net_device_ops', 'ndo_validate_addr', (10, 10, 10, 11)),
        ('block_device_operations', 'rw_page', (3, 4, None, None)),
        ('platform_driver', 'probe', (0, 0, 0, 0)),
        ('platform_driver', 'remove', (1, 1, 1, 1)),
        ('device_driver', 'probe', (8, 8, 8, 8)),
        ('net_device_ops', 'ndo_open', (2, 2, 2, 2)),
    ]
    for st, h, e in expected_index:
        chk('Table 10 index', f'{st}.{h}', e, idx(st, h))
    chk('Table 10 index', '6.9 rule 10 = compat_ioctl', 'compat_ioctl',
        H['file_operations']['6.9'][10])
    chk('Table 10 index', '7.1 rule 2/3 = llseek/read', ('llseek', 'read'),
        (H['file_operations']['7.1'][2], H['file_operations']['7.1'][3]))
    chk('Table 10 index', '7.1 ndo rule 10 = ndo_set_mac_address', 'ndo_set_mac_address',
        H['net_device_ops']['7.1'][10])


def check_struct_drift():
    """Ch. 1 / Table 10 / Table 1: bitcode struct field-count drift and the UAFX kernel_sts list."""
    sd = json.load(open(f'{EPI}/struct_drift_full.json'))
    if isinstance(sd, dict) and all(isinstance(sd[v], dict) for v in sd):
        com33 = set.intersection(*[set(sd[v]) for v in HDR_VERSIONS])

        def field_count(x):
            return x if not isinstance(x, (list, dict)) else len(x)

        ch = sum(1 for s in com33 if len({field_count(sd[v][s]) for v in HDR_VERSIONS}) > 1)
        chk('Ch. 1/Table 10', 'bitcode struct field counts: 25 of 33 changed', (33, 25),
            (len(com33), ch),
            note='epi_regfn/struct_drift_full.json (preliminary measurement on the LLVM16 full '
                 'tree)')
    ks = json.load(open(f'{EPI}/uafx_kernel_sts.json'))
    chk('Ch. 1/Table 1', 'kernel_sts entries/structs', (88, 51), (len(ks), len({x[0] for x in ks})))


# ---------------------------------------------------------------- 9. link layer, Ch. 4, perf, …
def check_link_layer_stats():
    """5.9 / 5.3: link-layer results (analyze3/behavior/atfinal json) and linked bitcode counts."""
    a3_path = f'{NOSAN}/analyze3.json' if E('FPEA_RESULTS') else f'{PASSD}/analyze3.json'
    a3 = json.load(open(a3_path))
    bh = json.load(open(f'{NOSAN}/behavior.json'))
    af = json.load(open(f'{NOSAN}/atfinal.json'))
    chk('5.9(b)', 'entry points/defined/miss rate', (139678, 249121, 96.24),
        (a3['FPEA'], a3['defined'], round(a3['miss'] * 100, 2)))
    chk('5.9(c)', 'framework-optable/lifecycle/user-triggered/interrupt',
        (58130, 12717, 16451, 2439),
        tuple(bh['cls'][k]
              for k in ('framework-optable', 'lifecycle', 'user-triggered', 'interrupt')))
    chk('Ch. 1', 'configfs_attribute / clk_ops (link-layer behavior top)', (1075, 1031),
        (bh['top']['framework-optable']['struct.configfs_attribute'],
         bh['top']['framework-optable']['struct.clk_ops']))
    chk('3.7 / Table S2', 'address-taken 143,632 (analyze3.json; the pair quoted in the text)',
        143632, a3['AT'])
    chk('3.7 / Table S2', 'AT only 16,556 (analyze3.json)', 16556, a3['onlyAT'])
    chk('3.7', 'FPEA = AT - AT-only + C2-only (139,678)', a3['FPEA'],
        a3['AT'] - a3['onlyAT'] + 12602)
    info('3.7 caution', 'AT / F of atfinal.json (different file set)', (af['AT'], af['F']),
         'atfinal.json analyses a different set (substitute units for FAIL modules; run time): '
         'AT 144,294. The text cites analyze3.json (143,632 / 139,678 / 16,556) only')
    if os.path.isdir(LINKBC):
        nmod = len(glob.glob(f'{LINKBC}/modules/*.bc'))
        nbi = len(glob.glob(f'{LINKBC}/builtin/*.bc'))
    else:
        all_files = open(ALLF).read().split()
        nmod = sum('/modules/' in x for x in all_files)
        nbi = sum('/builtin/' in x for x in all_files)
    n_fail = sum(1 for l in open(LINKREP or f'{LINKBC}/link_report.txt') if l.startswith('FAIL'))
    chk('5.9', '.mod 6,865 = linked 6,853 + failed 12; builtin 1,925', (6853, 12, 1925),
        (nmod, n_fail, nbi),
        note='the "6,865 modules" in skeleton 5.9 is the .mod count; bitcode is 6,853')
    chk('5.9', 'link-layer FPEA output count (fpea_out, modules+builtin)', 8778,
        len([x for x in os.listdir(LINKOUT) if 'linked-nosan14' in x]),
        note='the earlier 8,790 is .mod 6,865+1,925; actual analysed files 6,853+1,925=8,778 '
             '(+substitute units for failed modules)')
    chk('5.3 caution',
        'analyze3 wl_miss (link-layer WmF 424) IOCTL_CAND|external / INT_HANDLER_T|external',
        (314, 58), (a3['wl_miss']['IOCTL_CAND|external'], a3['wl_miss']['INT_HANDLER_T|external']),
        note='text 5.3 uses the unit-layer 987 together with this link-layer breakdown, mixing '
             'layers → recompute the unit-layer breakdown with --heavy')


def check_build_stats():
    """Ch. 4: kernel build counts (all.log), the unit list and the .o files without bitcode."""
    al = open(f'{NOSAN}/all.log').read()
    chk('Ch. 4', 'allmodconfig modules (llvm14)', 8519,
        int(re.search(r'llvm14\] config OK: modules (\d+)', al).group(1)))
    chk('Ch. 4', 'drivers .o / wllvm .bc', (16849, 15521),
        tuple(int(x) for x in
              re.search(r'llvm14\] build done: \.o (\d+), \.bc\(wllvm\) (\d+)', al).groups()))
    chk('Ch. 4', 'units.txt = drivers 15,520 + scripts 1 + tools 1', (15520, 2),
        (sum('/drivers/' in l for l in open(UNITS)),
         sum('/drivers/' not in l for l in open(UNITS) if l.strip())),
        note='differs by 1 from the drivers .bc 15,521 in all.log: the unit list is 15,520 '
             'drivers + 2 non-drivers')
    mb = [l.strip() for l in open(f'{FIN}/missing_bc_objects.txt') if l.strip()]
    chk('Ch. 4', '.o without bc', 1328, len(mb))
    # composite link object classification: composite if the Makefile in the same directory has
    # <name>-y / <name>-objs
    comp = 0
    nosrc = 0
    for o in mb:
        d, b = os.path.dirname(o), os.path.basename(o)[:-2]
        mk = f'{SRC517}/{d}/Makefile'
        txt = open(mk, errors='replace').read() if os.path.exists(mk) else ''
        pattern = r'^\s*' + re.escape(b).replace(r'\-', '[-_]') + r'[-_](y|objs|m)\b'
        if re.search(pattern, txt, re.M):
            comp += 1
        elif not os.path.exists(f'{SRC517}/{d}/{b}.c'):
            nosrc += 1
    if os.path.isdir(SRC517):
        chk('Ch. 4', 'composite link objects / no C source', (1275, 53), (comp, nosrc),
            note='Makefile <name>-y/-objs rules re-parsed')
    else:
        info('Ch. 4', 'composite link objects / no C source (1,275 / 53)', 'skipped',
             note=f'5.17.11 source tree {SRC517} not present — Makefile re-parsing only on the '
                  'measurement server')
    chk('Ch. 4', 'objects with a matching .c but no bc', 0, len(mb) - comp - nosrc)


def check_timing():
    """Table 15: FPEA run times (fpea_timing.txt) and the UAFX run time (version_measure.log)."""
    t = dict(l.split() for l in open(f'{FIN}/fpea_timing.txt') if len(l.split()) == 2)
    chk_t('Table 15', 'sequential/parallel s', (179.9, 16.4),
          (round(float(t['sequential_wall_sec']), 1), round(float(t['parallel14_wall_sec']), 1)))
    chk_t('Table 15', 'ms per unit', 11.6, round(float(t['sequential_wall_sec']) / 15522 * 1000, 1))
    vm = open(f'{FIN}/version_measure.log').read()
    chk_t('Table 15', 'UAFX 5.17.11 14-way parallel s', 37,
          int(re.search(r'\[5\.17\.11\] UAFX done (\d+)s', vm).group(1)))
    chk('Table 15', 'speed-up vs UAFX', 2.3, round(37 / 16.4, 1))


def check_intro_and_filter():
    """Ch. 1 entry surface (intro_stats.json), 3.4 filter validation, 3.3/5.10 C3 over-estimate."""
    st = json.load(open(f'{EPI}/intro_stats.json'))
    chk('Ch. 1 entry surface', 'syscall/ioctl uapi/all/fops/ops/init/exit/irq',
        (362, 1914, 2229, 1734, 3831, 2053, 2462, 3488),
        tuple(st[k] for k in ('syscalls', 'ioctl_uapi', 'ioctl_all', 'fops_def', 'ops_def',
                              'module_init', 'module_exit', 'request_irq')))
    fv = json.load(open(f'{EPI}/filter_validate.json'))
    chk_t('3.4 filter', '400 modules 8,429 / 96.0% / over 332 / missed 4',
          (400, 8429, 96.0, 332, 4),
          (fv['modules'], fv['total'], round(fv['agree'] / fv['total'] * 100, 1),
           fv['cm'].get('(True, False)', 0), fv['cm'].get('(False, True)', 0)),
          note='400-module sample from the debug (-g) build tree (os.walk order = filesystem '
               'order, so the sample differs per machine); rerun re-runs it on the build_kernel.sh '
               'dbg tree and records it as INFO alongside; if the tree is absent run_all.sh keeps '
               'the stored copy')
    fr_ = json.load(open(f'{NOSAN}/fp_refine.json'))
    chk('3.3/5.10', 'C3 synchronous-callback over-estimate 1,092', 1092, fr_['fp'],
        note='link-layer measurement (F 138,376 before the EXPORT fix)')


def check_uaf_subset():
    """Table 13: UAF-related subsets of the FPEA set (uaf_subset_unit.json)."""
    us = json.load(open(f'{FIN}/uaf_subset_unit.json'))['agg']
    chk('Table 13', 'FPEA total n/free/v1/v2/any1/any2',
        (129967, 12942, 41822, 29526, 48258, 38176),
        tuple(us[k] for k in ('E_n', 'E_free', 'E_shared_v1', 'E_shared_v2', 'E_any_v1',
                              'E_any_v2')))
    chk('Table 13', 'missed n/free/v1/v2/any1/any2', (125055, 12388, 40262, 28435, 46447, 36790),
        tuple(us[k] for k in ('M_n', 'M_free', 'M_shared_v1', 'M_shared_v2', 'M_any_v1',
                              'M_any_v2')))
    chk('Table 13', 'share %', (29.4, 37.1, 29.4, 37.1, 15.7, 19.9),
        (round(us['E_any_v2'] / us['E_n'] * 100, 1), round(us['E_any_v1'] / us['E_n'] * 100, 1),
         round(us['M_any_v2'] / us['M_n'] * 100, 1), round(us['M_any_v1'] / us['M_n'] * 100, 1),
         round(us['E_any_v2'] / 242823 * 100, 1), round(us['E_any_v1'] / 242823 * 100, 1)))
    chk('Table 13', 'M_n = FPEA − intersection', 129967 - 4912, us['M_n'])


def check_subsystem_ratios(VR):
    """Table 16: FPEA/defined ratio per driver subsystem; subsystem_ratio.json."""
    sub = defaultdict(lambda: [0, 0])
    for f, d in VR['5.17.11']['per_unit'].items():
        if '/drivers/' not in f:
            continue
        s = relkey(f).split('/')[0]
        sub[s][0] += d['defined']
        sub[s][1] += len(d['entries'])
    subj = {x['subsystem']: x for x in json.load(open(f'{FIN}/subsystem_ratio.json'))}
    expected = {'watchdog': 90.4, 'hwmon': 88.0, 'rtc': 87.9, 'gpio': 85.3, 'iio': 80.6,
                'input': 77.0, 'hid': 73.5, 'tty': 71.6, 'media': 63.6, 'usb': 54.5,
                'scsi': 45.0, 'gpu': 45.0, 'net': 44.2, 'md': 42.5, 'staging': 34.7,
                'acpi': 34.2, 'infiniband': 28.6}
    for s, e in expected.items():
        chk('Table 16 subsystem', s, e, round(sub[s][1] / sub[s][0] * 100, 1))
        chk('subsystem_ratio.json', s, (subj[s]['defined'], subj[s]['fpea']), tuple(sub[s]))


def check_tca_pilot():
    """TCA pilot (top-caller filter) row counts; presence of placeholder_trigger.log."""
    tr = json.load(open(f'{FIN}/tca_pilot_rows.json'))
    tr = tr if isinstance(tr, list) else tr.get('rows', tr)
    c = Counter()
    for r in tr:
        c[(r['label'], 'pos' if r['pos'] else 'neg', (r['r'] or {}).get('n_callers') == 0)] += 1
    info('TCA pilot', 'rows', len(tr))
    chk('TCA pilot',
        'callers 0 among TP 218 / callers 0 among FP 37 / callers 0 among negatives labelled 0 '
        '(185) / callers 0 among ? 15',
        (210, 36, 105, 15),
        (c[('1', 'pos', True)], c[('0', 'pos', True)], c[('0', 'neg', True)],
         c[('?', 'neg', True)]),
        note='final/tca_pilot.log; direct caller count r')
    chk('5.4 placeholder', 'placeholder_trigger.log exists', True,
        os.path.exists(f'{FIN}/placeholder_trigger.log'))


# ---------------------------------------------------------------- 9b. v2.3 audit (2026-11-09)
def check_audit_v23(ref, pop):
    """Supplementary S5/S11 (negative pool, expansion estimator, bootstrap), Table S2 (AT-only
    tagging and the 80 author-judged cases), Table S3 (whitelist-only decomposition), Table 12
    row 1 (fpea14 = fpea16 on the same bitcode). Reads the result files written by
    scripts/orig/audit_v23/ (data/results; regenerated into out/ by derive)."""
    res = audit_result

    # --- negative pool (recon_pool2) and the two FN estimators / bootstrap (boot2)
    rp = res('recon_pool2.json')
    chk('5.2 / S11', 'stage-1 units / pool / zero units / max unit', (500, 3071, 122, 100),
        (rp['units'], rp['pool_total'], rp['zero_units'], rp['max_unit']))
    chk('5.2 / S11', 'pool = sum of per-unit sizes', rp['pool_total'],
        sum(len(v) for v in rp['pool'].values()))
    chk('5.2 / S11', 'all 200 negatives are members of the pool', 200, rp['sample_in_pool'])
    sizes = sorted(rp['M'].values())
    chk('S11', 'median pool size per unit', 2, sizes[len(sizes) // 2])
    chk('5.2', 'conditional inclusion probability 200/|pool(S)|', 0.065,
        round(200 / rp['pool_total'], 3))
    chk('5.2', 'unconditional inclusion probability (approx.)', 0.0021,
        round(500 / 15522 * 200 / rp['pool_total'], 4),
        note='500/15,522 x 200/3,071 (the text says approximately 0.0021)')
    chk('5.2', 'pool density of the selected units vs population (per unit)', (6.1, 6.9),
        (round(rp['pool_total'] / 500, 1), round(106548 / 15522, 1)))
    chk('5.2 / S5', 'two-phase expansion weight (15,522/500)(|pool|/200), conditional on the realised pool', 476.7,
        round(15522 / 500 * rp['pool_total'] / 200, 1))
    chk('5.2 / S5', 'expansion estimate of |N|: N_HT = 15,522/500 * |pool|', 95336,
        round(15522 / 500 * rp['pool_total']))
    b = res('boot2_results.json')['N_clean']
    chk('5.2 / S5', 'ratio estimator = expansion estimator calibrated to the known |N|: '
        'FN_HT * |N| / N_HT', 7991, round(b['FN_ht'] * 106548 / (15522 / 500 * rp['pool_total'])))
    chk('5.2', 'expansion estimator FN_S = |pool|/200 * 15', 230, round(b['FN_S']))
    chk('5.2', 'expansion estimator FN_HT = 15,522/500 * FN_S', 7150, round(b['FN_ht']))
    chk('5.2', 'recall (expansion estimator, sensitivity)', 0.944, r3(b['recall_ht']))
    chk('5.2', 'recall (ratio estimator) from boot2', 0.937, r3(b['recall_ratio']))
    chk('5.2 / S5', 'unit bootstrap 95% (ratio estimator)', (0.873, 0.984),
        tuple(r3(x) for x in b['boot_recall']))
    chk('S5', 'unit bootstrap 95% (TP fixed, negatives only)', (0.874, 0.985),
        tuple(r3(x) for x in b['boot_recall_negonly']))
    chk('5.2 / S5', 'unit bootstrap 95% (expansion estimator)', (0.874, 0.987),
        tuple(r3(x) for x in b['boot_recall_ht']))
    chk('5.2 / S5', 'design effect d', 4.34, round(b['deff'], 2))
    bb = res('boot2_results.json')
    chk('5.2', 'dcn10_hw_sequencer.c pool 59 / expected sample 3.8 / observed 8', (59, 3.8, 8),
        (len([v for k, v in rp['pool'].items() if k.endswith('/.dcn10_hw_sequencer.o.bc')][0]),
         round(bb['dcn10_expected'], 1), bb['fn_by_unit'].get('.dcn10_hw_sequencer.o.bc')))
    chk('5.2', 'FN 15 = 8 in one unit + 7 in 7 other units', (8, 7),
        (max(bb['fn_by_unit'].values()), sum(1 for v in bb['fn_by_unit'].values() if v == 1)))
    chk('S11', 'TP_hat / precision excl. / incl. C2 (boot2)', (119629, 0.912, 0.920),
        (round(bb['TPhat']), r3(bb['prec_ex']), r3(bb['prec_in'])))
    chk('Appendix H / S15', 'FN estimate range from Wilson 4.6-12.0% of |N|', (4900, 12800),
        tuple(round(x * 106548 / 100, -2) for x in (4.6, 12.0)),
        note='the text rounds to about 4,900 - 12,800')

    # --- AT-only tagging (Table S2) and the 80 author-judged cases
    at = res('at_only.json')
    chk('Table S2', 'AT-only pairs', 16556, at['n'])
    t = at['tags']
    chk('Table S2', 'EXPORT by-product globals only', 16266, t.get('export_addressable_only', 0))
    chk('Table S2', 'phi/select/ret result used immediately', 205, t.get('select_phi_ret(+)', 0))
    chk('Table S2', 'icmp comparison only (4 + 1)', 5,
        t.get('icmp_only', 0) + t.get('export+icmp+bitcastcall', 0))
    chk('Table S2', 'argument of a call through a function pointer', 80, t.get('call_arg(+)', 0))
    chk('Table S2', 'rule verdicts 16,476 + author verdicts 80 = 16,556', 16556,
        t.get('export_addressable_only', 0) + t.get('select_phi_ret(+)', 0)
        + t.get('icmp_only', 0) + t.get('export+icmp+bitcastcall', 0) + t.get('call_arg(+)', 0))
    # the three author-verdict files are stored results (data/results), never produced by a re-run
    uj = audit_result('at_only_unit_judgment.json')
    tot = uj['totals']
    chk('3.7 / Table S2', 'unit-boundary author verdict: entry points 51 = 15 + 36, sync 29',
        (51, 15, 36, 29),
        (tot['label1'], tot['label1_other_module'], tot['label1_other_unit'], tot['label0']))
    n_om = len(uj['label1_other_module']['list'])
    n_ou = sum(len(g['list']) for g in uj['label1_other_unit_same_module'].values())
    n_sc = sum(len(g['list']) for g in uj['label0_sync_callback'].values())
    chk('3.7 / Table S2', 'judgment lists: other module / other unit / sync = 15 / 36 / 29, sum 80',
        (15, 36, 29, 80), (n_om, n_ou, n_sc, n_om + n_ou + n_sc))
    chk('3.7', 'other-unit groups: libfc 16, efct 10, dvb-core 4, i915 3, gdmulte 2, dm-snapshot 1',
        [16, 10, 4, 3, 2, 1],
        sorted((len(g['list']) for g in uj['label1_other_unit_same_module'].values()),
               reverse=True))
    chk('3.7', 'sync groups: dm iterate_devices 22 + 7 others', (22, 7),
        (max(len(g['list']) for g in uj['label0_sync_callback'].values()),
         n_sc - max(len(g['list']) for g in uj['label0_sync_callback'].values())))
    judged = set(uj['label1_other_module']['list'])
    for g in list(uj['label1_other_unit_same_module'].values()) + list(uj['label0_sync_callback'].values()):
        judged |= set(g['list'])
    mj = audit_result('at_only_judgment.json')
    chk('3.7 / 5.10', 'kernel-module-boundary author verdict: entry points 15', 15,
        mj['summary']['author_judged_entries'])
    src = audit_result('at80_src.json')
    call80 = {r[1] for r in at['rows'] if _at_tag(r[2]) == 'call_arg(+)'}
    chk('Table S2', 'the 80 call_arg functions = at80_src.json = the judged functions',
        (80, True, True), (len(src), call80 == {x[1] for x in src}, call80 == judged))
    try:
        s50 = res('at_only_sample50.json')
    except FileNotFoundError:
        s50 = None
    if s50:
        info('Table S2', 'random 50 of the AT-only pairs (seed 2026): tags',
             dict(Counter(_at_tag(r[2]) for r in s50)),
             'the 2026-11-09 draw was 49 EXPORT by-products + 1 phi/select (no information)')

    # --- whitelist-only decomposition (Table S3)
    w = res('wl_only.json')
    chk('Table S3', 'UAFX pairs / unique / in FPEA / WL-only', (5899, 5118, 4912, 987),
        (w['W_pairs'], w['W_unique'], w['inter'], w['wl_only']))
    chk('Table S3', 'WL-only: IOCTL_CAND declared / defined, INT_HANDLER_T declared',
        (547, 289, 151),
        (w['decomp'].get('IOCTL_CAND|declared', 0), w['decomp'].get('IOCTL_CAND|defined', 0),
         w['decomp'].get('INT_HANDLER_T|declared', 0)))
    chk('Table S3', 'external pairs 698, most redundant ata_scsi_ioctl 91 units', (698, 91),
        (w['ext_pairs'], dict(map(tuple, w['ext_top'])).get('ata_scsi_ioctl')))
    x = res('wl_ext.json')
    chk('Table S3', 'external unique names / defined in drivers / outside drivers', (359, 355, 4),
        (x['ext_unique'], x['ext_in_drivers'], len(x['ext_outside_drivers'])))
    chk('Table S3', 'outside drivers/: compat_ptr_ioctl etc.',
        ['blkdev_compat_ptr_ioctl', 'compat_ptr_ioctl', 'hpet_rtc_interrupt', 'snd_pcm_lib_ioctl'],
        x['ext_outside_drivers'])
    chk('Table S3', 'FPEA identifies in the defining unit', 9, len(x['ext_fpea_hit_own_unit']))
    chk('Table S3', 'not identified in the defining unit: static-call trampolines / registered '
        'in another unit', (4, 342), (len(x['ext_static_call_trampolines']),
                                       x['ext_other_unit_registered']))
    chk('Table S3 / S6', 'other-unit registered: link layer recovers / not recovered', (304, 38),
        (x['ext_link_recovered'], len(x['ext_link_unrecovered'])))
    chk('Table S3', 'defined-in-unit 289 = tracepoint by-products 25 + real ioctl handlers 264',
        (25, 264), (len(x['defined_trace_artifacts']), x['defined_real']))
    chk('Table S3 / S6', 'real ioctl handlers: link layer recovers / remain', (224, 40),
        (x['defined_link_recovered'], len(x['defined_link_unrecovered'])))
    chk('5.3 / S6', 'shared handlers: row sums (342+264 / 304+224 / 38+40), by name '
        '(total / link recovered / remaining), names in both rows, unique functions of the 987',
        (606, 528, 78, 372, 304, 68, 234, 414),
        (x['shared_handlers_total'], x['shared_link_recovered'], x['shared_link_unrecovered'],
         x['shared_unique_total'], x['shared_unique_link_recovered'],
         x['shared_unique_link_unrecovered'], len(x['row_overlap_names']),
         x['wl_only_unique_functions']))
    chk('5.3', 'whitelist-side errors: tracepoint 25 + static-call 4 + outside drivers 4', 33,
        len(x['defined_trace_artifacts']) + len(x['ext_static_call_trampolines'])
        + len(x['ext_outside_drivers']))
    chk('5.10', 'inter-module examples (drm_ioctl, ata_scsi_ioctl, dvb_generic_ioctl) are among the 68 not recovered', True,
        {'drm_ioctl', 'ata_scsi_ioctl', 'dvb_generic_ioctl'} <= set(x['ext_link_unrecovered']))
    # --- why the 68 are not recovered (resid68.py, 2026-11-11): Section 5.3 / 5.10, S6 (b')
    r68 = res('resid68.json')
    chk('5.3 / 5.10 / S6', 'unrecovered 68: inter-module / unlinked module / direct-call only / other',
        (68, 29, 9, 30, 0),
        (r68['n'], r68['counts'].get('inter_module', 0), r68['counts'].get('unlinked_module', 0),
         r68['counts'].get('direct_call_only', 0),
         sum(v for k, v in r68['counts'].items()
             if k not in ('inter_module', 'unlinked_module', 'direct_call_only'))))
    chk('5.10 / S6', 'examples: drm_ioctl, ata_scsi_ioctl, dvb_generic_ioctl inter-module; scsi_ioctl, cdrom_ioctl direct-call only',
        ('inter_module',) * 3 + ('direct_call_only',) * 2,
        tuple(r68['classes'][f] for f in ('drm_ioctl', 'ata_scsi_ioctl', 'dvb_generic_ioctl',
                                           'scsi_ioctl', 'cdrom_ioctl')))
    chk('S6', 'drm_ioctl / ata_scsi_ioctl: files of other modules taking the address', (54, 91),
        (len(r68['detail']['drm_ioctl']['at_other']), len(r68['detail']['ata_scsi_ioctl']['at_other'])))

    # --- fpea14 = fpea16 on the same bitcode (Table 12 row 1, Section 5.5 first axis)
    tm = res('typed_mode_cmp.json')
    chk('Table 12 / 5.5 axis 1', 'fpea14 = fpea16 on the LLVM 14 bitcode', (129967, 129967),
        (tm['fpea14'], tm['fpea16']))
    chk('Table 12 / 5.5 axis 1', 'differing units / only14 / only16 / label diff / defined diff',
        (0, 0, 0, 0, 0), (tm['diff_units'], tm['only14'], tm['only16'], tm['sigdiff'],
                          tm['defdiff']))
    chk('Table 12 / 5.5 axis 1', 'units compared', 15522, 15522 - tm.get('missing', 0))


def _at_tag(c):
    """Tag of one AT-only row (same rules as scripts/orig/audit_v23/at_only.py)."""
    ks = set(c)
    if ks == {'export_addressable'}:
        return 'export_addressable_only'
    if ks <= {'export_addressable', 'ksymtab', 'llvm_used', 'global_ptrtoint'}:
        return 'export_artifacts_only'
    if ks == {'icmp'}:
        return 'icmp_only'
    if ks <= {'export_addressable', 'ksymtab', 'llvm_used', 'global_ptrtoint', 'icmp',
              'bitcast_direct_call'}:
        return 'export+icmp+bitcastcall'
    for k, t in (('global_init_other', 'global_init_other(+)'), ('store', 'store(+)'),
                 ('call_arg', 'call_arg(+)'), ('select_phi_ret', 'select_phi_ret(+)')):
        if k in ks:
            return t
    return 'other'


# ---------------------------------------------------------------- 10. heavy: IR re-interpretation
# The pool workers must be module-level functions (they are pickled by name).
def classify_wl_unit(item):
    """Worker: classify the UAFX-only functions of one unit by their definition in the IR."""
    f, fns = item
    ll = dis14(f)
    dec = set(re.findall(r'^declare[^@]*@([\w.$]+)\(', ll, re.M))
    dfn = set(re.findall(r'^define[^@]*@([\w.$]+)\(', ll, re.M))
    out = []
    for fn in fns:
        if fn in dfn:
            cls = 'defined_not_FPEA'
        elif fn in dec:
            cls = 'external_declared'
        else:
            cls = 'other'
        out.append((f, fn, cls))
    return out


def iterator_only_count(item):
    """Worker: C3-only functions of one unit whose address only reaches iterator-type APIs."""
    f, fns = item
    ll = dis14(f)
    callees = defaultdict(set)
    for m in re.finditer(r'\bcall\b[^\n]*?@([\w.$]+)\(([^\n]*)\)', ll):
        for x in re.findall(r'(?<![\w.])@([\w.$]+)(?![\w.(])', m.group(2)):
            if x in fns:
                callees[x].add(m.group(1))
    return sum(1 for fn in fns
               if callees.get(fn) and all(ITER_API_RE.match(c) for c in callees[fn]))


def heavy_wl_breakdown(VR):
    """(a) unit-layer WL\\FPEA 987 breakdown: defined but not FPEA / external / other."""
    W517 = VR['5.17.11']
    todo = defaultdict(list)
    for (f, fn) in W517['Wset'] - W517['Fset']:
        todo[f].append(fn)
    kindof = {}
    for f in todo:
        for l in open(f'{rw_dir("5.17.11")}/{f.replace("/", "_")}.txt', errors='replace'):
            q = l.strip().split(':')
            if len(q) >= 2:
                kindof[(f, q[1])] = q[0]
    C = Counter()
    with ProcessPoolExecutor(nproc()) as ex:
        for res in ex.map(classify_wl_unit, list(todo.items()), chunksize=4):
            for f, fn, c in res:
                C[(kindof[(f, fn)], c)] += 1
    chk('Table S3 heavy', 'unit-layer WL∖FPEA 987 breakdown (kind|class: n)',
        {'IOCTL_CAND|external_declared': 547, 'IOCTL_CAND|defined_not_FPEA': 289,
         'INT_HANDLER_T|external_declared': 151},
        {f'{k}|{c}': n for (k, c), n in C.items()})


def heavy_iterator_only(pop):
    """(b) of the 8,798 C3-only functions, those used only by iterator-type APIs (726 in an earlier count)."""
    c3u = defaultdict(set)
    for f, fn in pop.c3only_set:
        c3u[f].add(fn)
    tot = 0
    with ProcessPoolExecutor(nproc()) as ex:
        for r in ex.map(iterator_only_count, list(c3u.items()), chunksize=8):
            tot += r
    chk('Table 2 auxiliary heavy', 'C3-only used only by iterator-type APIs', 677, tot, tol=0,
        note='definition: every call taking the address as an argument matches ITER (fp_audit.py '
             'regex); the earlier 726 is not reproducible')
    chk('Table 2 auxiliary', 'iterator share %', 0.52, round(tot / pop.nF * 100, 2))


def heavy_ath12k(VR):
    """(c) ath12k: mac unit of 6.9 (@ath12k_ops) and of 7.1.4-norand (ath12k_mac_op_*)."""
    mac69 = [f for f in VR['6.9']['per_unit'] if f.endswith('/wireless/ath/ath12k/mac.o.bc')]
    if mac69:
        d = VR['6.9']['per_unit'][mac69[0]]
        ll = dis14(mac69[0])
        m = re.search(r'^@ath12k_ops = [^\n]*', ll, re.M)
        ops = set(re.findall(r'@([\w.$]+)', m.group(0))) if m else set()
        chk('5.10 ath12k', '6.9 mac unit FPEA / C1 in @ath12k_ops', (45, 34),
            (len(d['entries']),
             sum(1 for fn, s in d['entries'].items() if 'C1' in s and fn in ops)))
    per_unit71 = VR['7.1.4-norand']['per_unit']
    mac71 = [f for f in per_unit71 if f.endswith('/wireless/ath/ath12k/mac.o.bc')]
    n71 = sum(1 for f in per_unit71 if '/wireless/ath/ath12k/' in f)
    if mac71:
        d = per_unit71[mac71[0]]
        ll = dis16(mac71[0])
        chk('5.10 ath12k', '7.1.4 ath12k .o.bc / mac unit C1 / ath12k_mac_op_* defined',
            (48, 0, 40),
            (n71, sum(1 for fn, s in d['entries'].items() if 'C1' in s),
             len(re.findall(r'^define[^@]*@ath12k_mac_op_\w+\(', ll, re.M))))


def heavy_case_studies(VR):
    """(d) case studies of Table 14: tlclk and docg3 units of 5.17.11."""
    per_unit = VR['5.17.11']['per_unit']
    tl = [f for f in per_unit if f.endswith('/char/.tlclk.o.bc')][0]
    dg = [f for f in per_unit if f.endswith('/mtd/devices/.docg3.o.bc')][0]
    e = per_unit[tl]['entries']
    wt = open(f'{rw_dir("5.17.11")}/{tl.replace("/", "_")}.txt').read()
    chk('Table 14 tlclk', 'cleanup_module C2 / tlclk_interrupt C3', (True, True),
        ('C2' in e.get('cleanup_module', {}), 'C3' in e.get('tlclk_interrupt', {})))
    chk('Table 14 tlclk',
        'UAFX (unit): tlclk_interrupt INT_HANDLER_T, tlclk_read READ_HDR, cleanup_module missed',
        (True, True, False),
        ('INT_HANDLER_T:tlclk_interrupt' in wt, 'READ_HDR:tlclk_read' in wt,
         ':cleanup_module' in wt),
        note='the earlier miss result is from the KASAN build output')
    e = per_unit[dg]['entries']
    wd = open(f'{rw_dir("5.17.11")}/{dg.replace("/", "_")}.txt').read().strip()
    chk('Table 14 docg3', 'docg3_release C1 / UAFX 0', (True, ''),
        ('C1' in e.get('docg3_release', {}), wd))
    chk('Table 14 tlclk', 'unit defined functions 28 = entry points 28', (28, 28),
        (per_unit[tl]['defined'], len(per_unit[tl]['entries'])))


# ---------------------------------------------------------------- report
def jsonable(v):
    """Convert sets/tuples/dict keys so that the computed values can be json-dumped."""
    if isinstance(v, set):
        return sorted(v)
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    return v


def write_report(out_path, json_path):
    """Write the markdown report / json values and print the summary to stdout.
    Returns the number of MISMATCH rows (the process exit status is 1 when it is not 0)."""
    ok = sum(r[4] == 'OK' for r in rows)
    bad = [r for r in rows if r[4] == 'MISMATCH']
    n_info = sum(r[4] == 'INFO' for r in rows)
    out = ['# Numeric verification report (verify_numbers.py)', '',
           f'- checks {sum(r[4] != "INFO" for r in rows)}: OK {ok}, MISMATCH {len(bad)}, '
           f'INFO {n_info}', '']
    if bad:
        out += ['## MISMATCH', '', '| section | item | expected (paper) | recomputed | note |',
                '|---|---|---|---|---|']
        out += [f'| {s} | {i} | {e} | {a} | {n} |' for s, i, e, a, _, n in bad]
        out.append('')
    out += ['## All checks', '',
            '| status | section | item | expected (paper) | recomputed | note |',
            '|---|---|---|---|---|---|']
    out += [f'| {st} | {s} | {i} | {e} | {a} | {n} |' for s, i, e, a, st, n in rows]
    txt = '\n'.join(out) + '\n'
    if out_path:
        with open(out_path, 'w') as fh:
            fh.write(txt)
    if json_path:
        with open(json_path, 'w') as fh:
            json.dump({k: jsonable(v) for k, v in computed.items()}, fh, ensure_ascii=False,
                      indent=1, default=str)
    print(f'OK {ok}  MISMATCH {len(bad)}  INFO {n_info}')
    for s, i, e, a, _, n in bad:
        print(f'  MISMATCH [{s}] {i}: expected {e} / recomputed {a}  {n}')
    for s, i, e, a, st, n in rows:
        if st == 'INFO':
            print(f'  INFO [{s}] {i}: {a}  {n}')
    return len(bad)


def main():
    args = parse_args()
    VR = check_version_table()
    check_first_measurement(VR)
    check_uafx_kinds(VR)
    check_randstruct_control(VR)
    pop = check_strata(VR)
    ref = load_reference_set()
    check_reference_set(VR, ref)
    check_labels_and_agreement(ref)
    check_precision(ref, pop)
    check_recall(ref, pop)
    check_fp_types(ref)
    check_rule_distributions(ref)
    check_sample_reproduction(VR, ref)
    check_link_layer_q15(ref)
    check_typed_vs_opaque(VR)
    check_hit_rates()
    check_named_literal()
    check_placeholder_units()
    check_kind_drift()
    check_header_offsets()
    check_struct_drift()
    check_link_layer_stats()
    check_build_stats()
    check_timing()
    check_intro_and_filter()
    check_uaf_subset()
    check_subsystem_ratios(VR)
    check_tca_pilot()
    check_audit_v23(ref, pop)
    if args.heavy:
        heavy_wl_breakdown(VR)
        heavy_iterator_only(pop)
        heavy_ath12k(VR)
        heavy_case_studies(VR)
    return write_report(args.out, args.json)


if __name__ == '__main__':
    # exit status 1 on any MISMATCH, so that run_all.sh and CI see the failure (INFO rows do
    # not count); an exception in a check propagates as a traceback (exit status 1 as well)
    sys.exit(1 if main() else 0)

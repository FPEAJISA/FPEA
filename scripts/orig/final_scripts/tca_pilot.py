"""Reference set, 455 items: number of direct callers within the unit vs final label
(top-caller filter pilot). Disassembles each unit's clang14 bitcode with llvm-dis and counts,
per reference function, the distinct defining functions that call it in the same unit.
Run with cwd = $FINS by run_all.sh pilots: `python3 tca_pilot.py > $FIN/tca_pilot.log`;
writes pilot_rows.json next to this script (copied to $FIN/tca_pilot_rows.json)."""
import csv
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor

DIS = '/home/user/llvm-14.0.7/bin/llvm-dis'
SRC = '/home/user/rerun/nosan/src14/linux-5.17.11/'
E = '/home/user/fpea_gt/expert_pkg/'
ANSWER_PATH = '/home/user/rerun/fpea_pass/gt_answer_unit.json'
N_WORKERS = 14
DIS_TIMEOUT = 600
# `define <attrs> @name(` line of the textual IR: group 1 = linkage/attributes, group 2 = name
DEFINE_RE = re.compile(r'define\s+(.*?)@([\w.$]+)\(')
STRATA = ['C1', 'C4only', 'C3', 'C5']


def read_rows_by_id(path):
    """Expert CSV -> {id: row dict} (columns keep their Korean names)."""
    return {r['id']: r for r in csv.DictReader(open(path, encoding='utf-8-sig'))}


def final(A, B, adj, i):
    """(final label, rule): the common verdict of A and B, else the adjudicator's."""
    if A[i]['verdict'] == B[i]['verdict']:
        return A[i]['verdict'], A[i]['rule']
    return adj[i]['adjudicated_verdict'], adj[i]['adjudicated_rule']


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


def bcpath(um, i):
    """Bitcode path of item i's unit (unit_map cmd = drivers/x/.name.o.cmd -> .../.name.o.bc)."""
    cmd = um[i]['cmd']
    return SRC + cmd[:-4] + '.bc'


def call_pattern(fn):
    """call/invoke of @fn (not a longer symbol ending in fn) on one IR line."""
    return re.compile(r'\b(?:call|invoke)\b[^\n]*?(?<![\w.$])@' + re.escape(fn) + r'\(')


def analyze(args):
    """Worker: (bc path, function names) -> (bc path, {fn: caller stats} or None if no bc)."""
    bc, fns = args
    if not os.path.exists(bc):
        return bc, None
    ll = subprocess.run([DIS, '-o', '-', bc], capture_output=True, text=True,
                        timeout=DIS_TIMEOUT).stdout
    res = {}
    for fn in fns:
        callers = set()
        self_rec = 0
        cur = None
        linkage = None
        defined = False
        pat = call_pattern(fn)
        for line in ll.split('\n'):
            m = DEFINE_RE.match(line)
            if m:
                cur = m.group(2)
                if cur == fn:
                    defined = True
                    linkage = 'internal' if 'internal' in m.group(1).split() else 'external'
                continue
            if line.startswith('}'):
                cur = None
                continue
            if cur and pat.search(line):
                if cur == fn:
                    self_rec += 1
                else:
                    callers.add(cur)
        res[fn] = dict(defined=defined, linkage=linkage, n_callers=len(callers),
                       callers=sorted(callers)[:5], self_rec=self_rec)
    return bc, res


def count_callers(ans, um):
    """Run analyze() over every unit of the reference set -> {bc path: per-function stats}."""
    bybc = defaultdict(set)
    for i in ans:
        bybc[bcpath(um, i)].add(ans[i]['fn'])
    out = {}
    with ProcessPoolExecutor(N_WORKERS) as ex:
        for bc, res in ex.map(analyze, list(bybc.items())):
            out[bc] = res
    return out


def build_rows(ans, um, A, B, adj, out):
    """One row per reference item (sorted by id) joining the answer key, label and stats."""
    rows = []
    for i in sorted(ans):
        a = ans[i]
        bc = bcpath(um, i)
        r = (out.get(bc) or {}).get(a['fn'])
        lab, rule = final(A, B, adj, i)
        rows.append(dict(id=i, fn=a['fn'], pos=a['fpea_positive'],
                         stratum=st(a['signals']) if a['fpea_positive'] else '-',
                         signals=a['signals'], label=lab, rule=rule, bc=bc, r=r))
    return rows


def tab(title, sel):
    """Print one tally line: items with caller=0 vs caller>0 among the defined ones."""
    c = Counter()
    for x in sel:
        if x['r'] and x['r']['defined']:
            c['caller>0' if x['r']['n_callers'] > 0 else 'caller=0'] += 1
    n = sum(c.values())
    print(f'{title:45} n={n:4} caller=0 {c["caller=0"]:4}  caller>0 {c["caller>0"]:4}')


def print_example(x):
    print(f" {x['id']} {x['fn']:40} {x['stratum']:6} {x['rule']:12} {x['r']['linkage']:8}"
          f" callers={x['r']['n_callers']} {x['r']['callers']}")


def print_tallies(rows):
    """The tally tables by label, stratum and rule, then the caller>0 examples."""
    pos = [x for x in rows if x['pos']]
    neg = [x for x in rows if not x['pos']]
    print('\n== FPEA positives 255 (by final label) ==')
    tab('TP (label 1)', [x for x in pos if x['label'] == '1'])
    tab('FP (label 0)', [x for x in pos if x['label'] == '0'])
    for s in STRATA:
        tab(f'  TP {s}', [x for x in pos if x['label'] == '1' and x['stratum'] == s])
        tab(f'  FP {s}', [x for x in pos if x['label'] == '0' and x['stratum'] == s])
    for rule in sorted({x['rule'] for x in pos if x['label'] == '0'}):
        tab(f'  FP rule={rule}', [x for x in pos if x['label'] == '0' and x['rule'] == rule])
    for rule in sorted({x['rule'] for x in pos if x['label'] == '1'}):
        tab(f'  TP rule={rule}', [x for x in pos if x['label'] == '1' and x['rule'] == rule])
    print('\n== Negatives 200 ==')
    tab('neg label 0', [x for x in neg if x['label'] == '0'])
    tab('neg label ? (other-file registration)', [x for x in neg if x['label'] == '?'])
    print('\n== TP with caller>0 (entry points lost by the filter), examples ==')
    for x in [x for x in pos if x['label'] == '1' and x['r'] and x['r']['n_callers'] > 0][:40]:
        print_example(x)
    print('\n== FP with caller>0 (FP removed by the filter) ==')
    for x in [x for x in pos if x['label'] == '0' and x['r'] and x['r']['n_callers'] > 0]:
        print_example(x)


def main():
    ans = json.load(open(ANSWER_PATH))
    um = json.load(open(E + 'unit_map_internal.json'))
    A = read_rows_by_id(E + 'rA.csv')
    B = read_rows_by_id(E + 'rB.csv')
    adj = read_rows_by_id(E + 'adjudication_17_final.csv')
    out = count_callers(ans, um)
    rows = build_rows(ans, um, A, B, adj, out)
    with open(os.path.dirname(os.path.abspath(__file__)) + '/pilot_rows.json', 'w') as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=1)
    missing = [x for x in rows if x['r'] is None]
    undef = [x for x in rows if x['r'] and not x['r']['defined']]
    print('rows', len(rows), 'bc missing', len(missing), 'fn undefined', len(undef))
    for x in missing[:5]:
        print(' miss', x['id'], x['fn'], x['bc'])
    for x in undef[:10]:
        print(' undef', x['id'], x['fn'], x['bc'])
    # tally
    print_tallies(rows)


if __name__ == '__main__':
    main()

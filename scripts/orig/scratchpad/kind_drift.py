#!/usr/bin/env python3
"""(c) Decomposition of the causes of the per-kind change in UAFX original-binary
identification counts (5.19.17 -> 6.9).

For units with the same relative path, trace the (kind, func) pairs present only in 5.19.17
in the 6.9 IR:
  A) function not defined in the 6.9 unit (code changed/moved)
  B) defined but in no global initializer
  C) in a rule-struct initializer but at a position other than the rule index (index shift)
  D) at the rule index of a rule-struct initializer (another cause on the tool side)
  E) only in an initializer of a struct not covered by a rule
Reads <SP>/rw_5.19.17, <SP>/rw_6.9, <SP>/list_6.9.txt and the 6.9 IR; prints the tallies and
writes $FPEA_HOME/fpea_gt/final/kind_drift_519_69.json.  Invoked as `python3 kind_drift.py`.
"""
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from multiprocessing import Pool

# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
HOME_ROOT = os.environ.get('FPEA_HOME') or os.path.expanduser('~')
TMP_ROOT = os.environ.get('FPEA_TMP', '/tmp')

DIS = '/usr/bin/llvm-dis-14'
DIS_TIMEOUT = 300
POOL_SIZE = 14
CHUNKSIZE = 4
SP = os.environ.get('FPEA_WORK') or f'{TMP_ROOT}/scratchpad'
T = {'5.19.17': f'{HOME_ROOT}/linux_bc/nosan-rb-5.19.17', '6.9': f'{HOME_ROOT}/linux_bc/nosan-rb-6.9'}
RULES_JSON = f'{HOME_ROOT}/epi_regfn/uafx_kernel_sts.json'
OUT_JSON = f'{HOME_ROOT}/fpea_gt/final/kind_drift_519_69.json'
MAX_EXAMPLES = 5
DEFINE_RE = re.compile(r'^define[^@]*@([\w.$]+)\(', re.M)
# global initializer of a named struct: `@name = ... %struct.X { fields } , align|section`
INIT_RE = re.compile(r'^@[\w.$]+\s*=[^\n]*?%(struct\.[\w.]+)\s*\{(.*)\}\s*,?\s*(align|section)',
                     re.M)

KS = json.load(open(RULES_JSON))
RULE = defaultdict(dict)   # struct -> idx -> kind
for st, i, k in KS:
    RULE[st.replace('struct.', '')][i] = k


def load(version):
    """relative unit name -> set of (kind, function) pairs from the baseline files."""
    result = {}
    for name in os.listdir(f'{SP}/rw_{version}'):
        if 'nosan-rb' in name:
            rel = name.split(f'nosan-rb-{version}_', 1)[-1]
        else:
            rel = name.split('linux-5.17.11_', 1)[-1]
        pairs = set()
        for line in open(f'{SP}/rw_{version}/{name}', errors='replace'):
            parts = line.strip().split(':')
            if len(parts) >= 2:
                pairs.add((parts[0], parts[1]))
        result[rel] = pairs
    return result


def split_top(body):
    """Split an initializer body at top-level commas (brackets of any kind nest)."""
    fields = []
    depth = 0
    cur = ''
    for ch in body:
        if ch in '{[(<':
            depth += 1
        elif ch in '}])>':
            depth -= 1
        if ch == ',' and depth == 0:
            fields.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        fields.append(cur)
    return fields


def rule_struct(st):
    """Rule-table key of an IR struct name (`file_operations.123` -> `file_operations`)."""
    return st.split('.')[0]


def one(args):
    """Pool worker: classify every lost (kind, function) of one unit against its 6.9 IR."""
    rel, path69, lost = args
    try:
        ll = subprocess.run([DIS, '-o', '-', path69], capture_output=True, text=True,
                            timeout=DIS_TIMEOUT).stdout
    except Exception:
        return [(k, f, 'X_dis_fail') for k, f in lost]
    defined = set(DEFINE_RE.findall(ll))
    # global initializers: struct name and top-level fields
    inits = []
    for m in INIT_RE.finditer(ll):
        inits.append((m.group(1).replace('struct.', ''), split_top(m.group(2))))
    out = []
    for kind, fn in lost:
        if fn not in defined:
            out.append((kind, fn, 'A_not_defined'))
            continue
        pat = re.compile(r'(?<![\w.])@' + re.escape(fn) + r'(?![\w.])')
        hits = []
        for st, fields in inits:
            for i, field in enumerate(fields):
                if pat.search(field):
                    hits.append((st, i))
        if not hits:
            out.append((kind, fn, 'B_no_initializer'))
            continue
        rule_hit = [(st, i) for st, i in hits if rule_struct(st) in RULE]
        if not rule_hit:
            out.append((kind, fn, 'E_struct_not_in_rule:' + hits[0][0]))
            continue
        exact = [(st, i) for st, i in rule_hit if RULE[rule_struct(st)].get(i) == kind]
        if exact:
            out.append((kind, fn, 'D_rule_index_matches:' + exact[0][0]))
            continue
        st, i = rule_hit[0]
        ridx = [j for j, k in RULE[rule_struct(st)].items() if k == kind]
        out.append((kind, fn, f'C_index_shift:{st}@{i} (rule {ridx})'))
    return out


def resolve_paths():
    """relative unit name (as in rw_6.9 file names) -> real 6.9 .bc path, from the list file."""
    paths = {}
    for line in open(f'{SP}/list_6.9.txt'):
        line = line.strip()
        paths[line.split('nosan-rb-6.9/', 1)[-1].replace('/', '_')] = line
    return paths


def main():
    a = load('5.19.17')
    b = load('6.9')
    common = set(a) & set(b)
    lost = Counter()
    gained = Counter()
    jobs = []
    for rel in common:
        lost_pairs = a[rel] - b[rel]
        gained_pairs = b[rel] - a[rel]
        for k, f in lost_pairs:
            lost[k] += 1
        for k, f in gained_pairs:
            gained[k] += 1
        if lost_pairs:
            jobs.append((rel, lost_pairs))
    print('common units', len(common), 'only 5.19', len(set(a) - set(b)),
          'only 6.9', len(set(b) - set(a)))
    print('lost by kind', dict(lost))
    print('gained by kind', dict(gained))

    # resolve real path from list file
    paths = resolve_paths()
    jobs2 = []
    for rel, lost_pairs in jobs:
        key = rel[:-4] if rel.endswith('.txt') else rel
        path69 = paths.get(key)
        if path69:
            jobs2.append((rel, path69, sorted(lost_pairs)))
    print('units with losses', len(jobs), 'resolved', len(jobs2))

    cause = Counter()
    examples = defaultdict(list)
    with Pool(POOL_SIZE) as pool:
        for out in pool.imap_unordered(one, jobs2, chunksize=CHUNKSIZE):
            for kind, fn, c in out:
                cc = c.split(':')[0]
                cause[(kind, cc)] += 1
                if len(examples[(kind, cc)]) < MAX_EXAMPLES:
                    examples[(kind, cc)].append((fn, c))
    print('\n[loss cause by kind]')
    for (k, c), n in sorted(cause.items()):
        print(f'  {k:14s} {c:24s} {n}')
    summary = dict(lost=dict(lost), gained=dict(gained),
                   cause={f'{k}|{c}': n for (k, c), n in cause.items()},
                   examples={f'{k}|{c}': v for (k, c), v in examples.items()})
    with open(OUT_JSON, 'w') as out:
        json.dump(summary, out, indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()

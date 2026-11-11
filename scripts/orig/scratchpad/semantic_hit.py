"""Semantic version of the designated-field hit rate for one kernel version.

Does the IR field pointed to by the rule (struct, 5.17-based index) (a) hold any function at
all (same as hitrate_full), (b) still point to the field the rule intended (5.17 header name),
(c) hold a function but a different field, (d) miss the intended handler because it sits at a
different index.  Invoked as `python3 semantic_hit.py <version> <bc tree> <header column>`
(header column 5.17/5.19/6.9/7.1 or 'rand'); prints one JSON line and writes
$FPEA_HOME/fpea_gt/final/semantic_hit_<version>.json.
"""
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from multiprocessing import Pool

# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
HOME_ROOT = os.environ.get('FPEA_HOME') or os.path.expanduser('~')
TMP_ROOT = os.environ.get('FPEA_TMP', '/tmp')

DIS = f'{HOME_ROOT}/llvm/build/bin/llvm-dis'
DIS_TIMEOUT = 120
POOL_SIZE = 14
CHUNKSIZE = 20
RULES_JSON = f'{HOME_ROOT}/epi_regfn/uafx_kernel_sts.json'
HEADER_JSON = f'{HOME_ROOT}/epi_regfn/handler_offset.json'
# global initializer of a named struct: `@name = ... %struct.X { fields } , align`
INIT_RE = re.compile(r'^@[\w.$]+\s*=[^\n]*?%(struct\.[\w.]+)\s*\{(.*)\}\s*,?\s*align', re.M)
FN_REF_RE = re.compile(r'@[\w.$]+')

# argv: version, bc tree, header column (5.17/5.19/6.9/7.1) or 'rand'; HV is used by the worker
VERSION, TREE, HV = sys.argv[1:4]
KS = json.load(open(RULES_JSON))
H = json.load(open(HEADER_JSON))   # struct -> header column -> field names
RULES = defaultdict(list)          # struct -> rule-designated indices
for st, idx, ty in KS:
    RULES[st].append(idx)


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


def one(bc):
    """Pool worker: per-unit counters (designated, has_fn, no_header, with_header, ...)."""
    r = defaultdict(int)
    try:
        ll = subprocess.run([DIS, '-o', '-', bc], capture_output=True, text=True,
                            timeout=DIS_TIMEOUT).stdout
    except:  # noqa: E722 - bare except kept as in the original (any failure counts nothing)
        return r
    for m in INIT_RE.finditer(ll):
        st = m.group(1)
        if st not in RULES:
            continue
        fields = split_top(m.group(2))
        name = st[7:]   # strip 'struct.'
        for i in RULES[st]:
            r['designated'] += 1
            has_fn = i < len(fields) and bool(FN_REF_RE.search(fields[i]))
            if has_fn:
                r['has_fn'] += 1
            if name not in H or HV == 'rand':
                r['no_header'] += 1
                continue
            r['with_header'] += 1
            # field name the 5.17 rule intended, and its index in the HV header column
            intended = H[name]['5.17'][i] if i < len(H[name]['5.17']) else None
            j = H[name][HV].index(intended) if (intended and intended in H[name][HV]) else None
            if j == i:
                r['index_same'] += 1
                if has_fn:
                    r['semantic_hit'] += 1
            else:
                r['index_moved'] += 1
                if has_fn:
                    r['wrong_field_fn'] += 1
                if j is not None and j < len(fields) and FN_REF_RE.search(fields[j]):
                    r['intended_missed'] += 1
    return r


def driver_units(tree):
    """All driver .o.bc files below the tree, in os.walk order."""
    return [os.path.join(root, f) for root, _, fs in os.walk(tree) for f in fs
            if f.endswith('.o.bc') and '/drivers/' in root + '/' + f]


def main():
    bcs = driver_units(TREE)
    totals = defaultdict(int)
    with Pool(POOL_SIZE) as pool:
        for r in pool.imap_unordered(one, bcs, chunksize=CHUNKSIZE):
            for k, v in r.items():
                totals[k] += v
    totals['units'] = len(bcs)
    totals['version'] = VERSION
    totals['header_col'] = HV
    d = dict(totals)
    d['rate_has_fn'] = round(d['has_fn'] / d['designated'] * 100, 2)
    if d.get('with_header'):
        d['rate_semantic_within_header'] = round(d['semantic_hit'] / d['with_header'] * 100, 2)
    print(json.dumps(d, ensure_ascii=False))
    with open(f'{HOME_ROOT}/fpea_gt/final/semantic_hit_{VERSION}.json', 'w') as out:
        json.dump(d, out, indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()

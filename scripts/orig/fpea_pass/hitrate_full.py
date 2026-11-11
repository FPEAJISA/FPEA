"""Designated-field hit rate of the UAFX rule set over one kernel version (all driver units).

For every global initializer of a rule struct, counts the rule-designated fields
(`designated`) and how many of them hold a function (`hit`).
Invoked as `python3 hitrate_full.py <version> <bc tree>`; prints one summary line and
writes $FPEA_HOME/rerun/nosan/hitfull_<version>.json.
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
# global initializer of a named struct: `@name = ... %struct.X { fields } , align`
INIT_RE = re.compile(r'^@[\w.$]+\s*=[^\n]*?%(struct\.[\w.]+)\s*\{(.*)\}\s*,?\s*align', re.M)
FN_REF_RE = re.compile(r'@[\w.$]+')

# struct -> set of rule-designated field indices
KS = json.load(open(RULES_JSON))
FIELDS = defaultdict(set)
for st, idx, ty in KS:
    FIELDS[st].add(idx)


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
    """Pool worker: (designated fields, function-valued designated fields) of one unit."""
    try:
        ll = subprocess.run([DIS, '-o', '-', bc], capture_output=True, text=True,
                            timeout=DIS_TIMEOUT).stdout
    except:  # noqa: E722 - bare except kept as in the original (any failure counts as 0/0)
        return (0, 0)
    designated = hit = 0
    for m in INIT_RE.finditer(ll):
        st = m.group(1)
        if st not in FIELDS:
            continue
        fields = split_top(m.group(2))
        for i in FIELDS[st]:
            designated += 1
            if i < len(fields) and FN_REF_RE.search(fields[i]):
                hit += 1
    return (designated, hit)


def driver_units(tree):
    """All driver .o.bc files below the tree, in os.walk order."""
    return [os.path.join(root, f) for root, _, fs in os.walk(tree) for f in fs
            if f.endswith('.o.bc') and '/drivers/' in root + '/' + f]


def main():
    version, tree = sys.argv[1:3]
    bcs = driver_units(tree)
    designated = hit = 0
    with Pool(POOL_SIZE) as pool:
        for dd, dh in pool.imap_unordered(one, bcs, chunksize=CHUNKSIZE):
            designated += dd
            hit += dh
    print(f"[{version}] all {len(bcs)} units: designated fields {designated},"
          f" function-valued {hit}, hit rate {hit/designated*100:.2f}%")
    summary = dict(version=version, designated=designated, hit=hit,
                   rate=round(hit/designated*100, 2))
    with open(f'{HOME_ROOT}/rerun/nosan/hitfull_{version}.json', 'w') as out:
        json.dump(summary, out)


if __name__ == '__main__':
    main()

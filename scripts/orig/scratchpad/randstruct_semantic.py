"""Semantic hit rate of the struct-name + field-index rules under the 7.1.4 RANDSTRUCT_FULL build.

semantic_hit.py cannot judge the RANDSTRUCT_FULL tree (header column 'rand': every slot is
no_header), because the header order says nothing about the randomised IR order.  This script
recovers the per-struct permutation from the IR itself: the same named global initializer is
paired in the RANDSTRUCT_NONE and RANDSTRUCT_FULL trees, and for every field value that occurs
exactly once on both sides (a function address, @__this_module, ...) the pair (NONE index,
FULL index) is a vote.  With the permutation, a rule slot i is a semantic hit when the intended
5.17 field (its NONE index taken from the 7.1 header column, as in semantic_hit.py) is permuted to
i and a function sits at i.  Slots whose intended field no longer exists are counted as index_moved,
as in semantic_hit.py.  The counters of semantic_hit.py are recomputed from the same extraction
as a consistency check (norand 7.1 / rand 'rand').

Invoked as `python3 randstruct_semantic.py [<NONE tree> <FULL tree>]` (defaults: the env.sh trees
FPEA_BC_714N / FPEA_BC_714, else $FPEA_HOME/linux_bc/nosan-rb-7.1.4{-norand,}).  Prints one JSON
line and writes $FPEA_HOME/fpea_gt/final/semantic_hit_7.1.4-randperm.json.  Measured 2026-11-20
(seed data/randstruct_7.1.4/randstruct.seed): semantic hit 2,436 / 9,185 = 26.52%, of which 2,433
come from file_operations.read being permuted to index 2 (= the 5.17 rule index) and 3 from
structs that RANDSTRUCT_FULL does not randomise (watchdog_ops, proto_ops); the expectation under a
uniform permutation of the randomised structs is 267.9 hits (2.92%).
"""
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from multiprocessing import Pool

# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
HOME_ROOT = os.environ.get('FPEA_HOME') or os.path.expanduser('~')

DIS = f'{HOME_ROOT}/llvm/build/bin/llvm-dis'
DIS_TIMEOUT = 120
POOL_SIZE = 16
CHUNKSIZE = 20
RULES_JSON = f'{HOME_ROOT}/epi_regfn/uafx_kernel_sts.json'
HEADER_JSON = f'{HOME_ROOT}/epi_regfn/handler_offset.json'
OUT_JSON = f'{HOME_ROOT}/fpea_gt/final/semantic_hit_7.1.4-randperm.json'
SEED_FILE = os.environ.get('FPEA_RANDSTRUCT_SEED', '')
TREE_NONE = (sys.argv[1] if len(sys.argv) > 2 else
             os.environ.get('FPEA_BC_714N') or f'{HOME_ROOT}/linux_bc/nosan-rb-7.1.4-norand')
TREE_FULL = (sys.argv[2] if len(sys.argv) > 2 else
             os.environ.get('FPEA_BC_714') or f'{HOME_ROOT}/linux_bc/nosan-rb-7.1.4')
# global initializer of a named struct: `@name = ... %struct.X { fields } , align`
INIT_RE = re.compile(r'^@([\w.$]+)\s*=[^\n]*?%(struct\.[\w.]+)\s*\{(.*)\}\s*,?\s*align', re.M)
FN_REF_RE = re.compile(r'@[\w.$]+')
KS = json.load(open(RULES_JSON))
H = json.load(open(HEADER_JSON))        # struct -> header column -> field names
RULES = defaultdict(list)               # struct -> [(index, kind)]
for st, idx, ty in KS:
    RULES[st].append((idx, ty))
# how RANDSTRUCT_FULL under clang 16 treats the 8 header-parsed structs (checked in the 7.1.4
# headers; clang auto-randomises only structs whose members are all function pointers)
LAYOUT_NOTE = {'file_operations': '__randomize_layout', 'tty_operations': '__randomize_layout',
               'rtc_class_ops': 'all function pointers (auto)',
               'snd_pcm_ops': 'all function pointers (auto)',
               'net_device_ops': 'not randomised (data member net_shaper_ops)',
               'watchdog_ops': 'not randomised (struct module *owner)',
               'block_device_operations': 'not randomised (owner, pr_ops)',
               'proto_ops': 'not randomised (family, owner)'}


def split_top(body):
    """Split an initializer body at top-level commas (brackets of any kind nest)."""
    fields, depth, cur = [], 0, ''
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
    return [f.strip() for f in fields]


def extract(rel):
    """Pool worker: {tree: {global: [struct, [field texts]]}} for the rule structs of one unit."""
    out = {}
    for key, root in (('none', TREE_NONE), ('full', TREE_FULL)):
        d = {}
        try:
            ll = subprocess.run([DIS, '-o', '-', os.path.join(root, rel)], capture_output=True,
                                text=True, timeout=DIS_TIMEOUT).stdout
        except Exception:  # any failure counts nothing, as in semantic_hit.py
            ll = ''
        for m in INIT_RE.finditer(ll):
            if m.group(2) in RULES:
                d[m.group(1)] = [m.group(2), split_top(m.group(3))]
        out[key] = d
    return rel, out


def legacy_counters(tree, hv):
    """The counters of semantic_hit.py recomputed from the extraction (consistency check)."""
    r = Counter()
    for gl in tree.values():
        for st, fields in gl.values():
            name = st[7:]
            for i, _ in RULES[st]:
                r['designated'] += 1
                has_fn = i < len(fields) and bool(FN_REF_RE.search(fields[i]))
                r['has_fn'] += has_fn
                if name not in H or hv == 'rand':
                    r['no_header'] += 1
                    continue
                r['with_header'] += 1
                intended = H[name]['5.17'][i] if i < len(H[name]['5.17']) else None
                j = H[name][hv].index(intended) if (intended and intended in H[name][hv]) else None
                if j == i:
                    r['index_same'] += 1
                    r['semantic_hit'] += has_fn
                else:
                    r['index_moved'] += 1
                    r['wrong_field_fn'] += has_fn
                    if j is not None and j < len(fields) and FN_REF_RE.search(fields[j]):
                        r['intended_missed'] += 1
    return dict(r)


def permutations(none, full):
    """Per struct: NONE index -> FULL index from the paired named globals, plus a report."""
    votes, paired, nfield, len_mismatch = defaultdict(Counter), Counter(), {}, Counter()
    for rel, gl in none.items():
        gf = full.get(rel, {})
        for g, (st, fn_) in gl.items():
            if g not in gf or gf[g][0] != st:
                continue
            ff = gf[g][1]
            if len(fn_) != len(ff):
                len_mismatch[st] += 1
                continue
            paired[st] += 1
            nfield[st] = len(fn_)
            cn, cf = Counter(fn_), Counter(ff)
            for j, v in enumerate(fn_):
                if cn[v] == 1 and cf.get(v, 0) == 1:   # values unique on both sides vote
                    votes[st][(j, ff.index(v))] += 1
    perm, report = {}, {}
    for st, vt in votes.items():
        byj = defaultdict(Counter)
        for (j, i), c in vt.items():
            byj[j][i] += c
        p, conflicts = {}, 0
        for j, cnt in byj.items():
            i, c = cnt.most_common(1)[0]
            p[j] = i
            conflicts += sum(cnt.values()) - c
        perm[st] = p
        report[st] = dict(nfield=nfield[st], paired=paired[st], resolved=len(p),
                          conflicts=conflicts, injective=len(set(p.values())) == len(p),
                          identity=all(j == i for j, i in p.items()),
                          len_mismatch=len_mismatch[st])
    return perm, report


def rand_semantic(full, perm):
    """Semantic counters of the FULL tree over the header-parsed structs, per rule and in total."""
    r, per_rule = Counter(), defaultdict(Counter)
    exp_hits = 0.0
    for gl in full.values():
        for st, fields in gl.values():
            name = st[7:]
            if name not in H:
                continue
            p = perm.get(st, {})
            randomised = report_is_randomised(st)
            for i, t in RULES[st]:
                key = f'{name}:{i}:{t}'
                r['with_header'] += 1
                per_rule[key]['slots'] += 1
                has_fn = i < len(fields) and bool(FN_REF_RE.search(fields[i]))
                per_rule[key]['has_fn'] += has_fn
                intended = H[name]['5.17'][i] if i < len(H[name]['5.17']) else None
                j = H[name]['7.1'].index(intended) if (intended and intended in H[name]['7.1']) else None
                ir = p.get(j) if j is not None else None
                if ir is not None and randomised:
                    exp_hits += 1.0 / len(fields)
                if ir == i:
                    r['index_same'] += 1
                    per_rule[key]['index_same'] += 1
                    r['semantic_hit'] += has_fn
                    per_rule[key]['semantic_hit'] += has_fn
                    if not randomised:
                        r['hits_from_non_randomised_structs'] += has_fn
                else:
                    r['index_moved'] += 1
                    r['wrong_field_fn'] += has_fn
                    per_rule[key]['wrong_field_fn'] += has_fn
                    if ir is not None and ir < len(fields) and FN_REF_RE.search(fields[ir]):
                        r['intended_missed'] += 1
                        per_rule[key]['intended_missed'] += 1
                    if ir is None:
                        per_rule[key]['intended_field_absent'] += 1
    r = dict(r)
    r['rate_semantic_within_header'] = round(100 * r.get('semantic_hit', 0) / r['with_header'], 2)
    r['hits_from_file_operations_read'] = per_rule['file_operations:2:READ_HDR'].get('semantic_hit', 0)
    r['expected_semantic_hits_uniform_perm'] = round(exp_hits + r.get('hits_from_non_randomised_structs', 0), 1)
    r['expected_rate_uniform_perm_pct'] = round(100 * r['expected_semantic_hits_uniform_perm'] / r['with_header'], 2)
    return r, {k: dict(v) for k, v in per_rule.items()}


_PERM_REPORT = {}


def report_is_randomised(st):
    rep = _PERM_REPORT.get(st)
    return bool(rep) and not rep['identity']


def main():
    rels = sorted(os.path.relpath(os.path.join(r, f), TREE_FULL)
                  for r, _, fs in os.walk(os.path.join(TREE_FULL, 'drivers'))
                  for f in fs if f.endswith('.o.bc'))
    none, full = {}, {}
    with Pool(POOL_SIZE) as pool:
        for rel, out in pool.imap_unordered(extract, rels, chunksize=CHUNKSIZE):
            if out['none']:
                none[rel] = out['none']
            if out['full']:
                full[rel] = out['full']
    perm, report = permutations(none, full)
    _PERM_REPORT.update(report)
    r, per_rule = rand_semantic(full, perm)
    legacy_full = legacy_counters(full, 'rand')
    d = dict(version='7.1.4', header_col='7.1 + recovered RANDSTRUCT permutation', units=len(rels),
             designated=legacy_full['designated'], has_fn=legacy_full['has_fn'],
             no_header=legacy_full['designated'] - r['with_header'],
             rate_has_fn=round(100 * legacy_full['has_fn'] / legacy_full['designated'], 2))
    d.update(r)
    if SEED_FILE and os.path.exists(SEED_FILE):
        d['randstruct_seed'] = open(SEED_FILE).read().strip()
    d['legacy_counters'] = {'7.1.4-norand (header 7.1)': legacy_counters(none, '7.1'),
                            '7.1.4 (header rand)': legacy_full}
    d['layout_note'] = LAYOUT_NOTE
    d['permutation_report'] = report
    d['permutation'] = {st: {str(j): i for j, i in sorted(p.items())} for st, p in perm.items()}
    d['per_rule'] = per_rule
    print(json.dumps({k: v for k, v in d.items() if not isinstance(v, dict)}, ensure_ascii=False))
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, 'w') as out:
        json.dump(d, out, indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()

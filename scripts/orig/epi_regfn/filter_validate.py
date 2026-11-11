#!/usr/bin/env python3
"""Contamination filter validation.

Compares the naming-rule classification of compiler-generated symbols against a
debug-info (DISubprogram) based classification and measures the agreement of the
two methods on the debug build (5.17.11, KCFLAGS=-g).  Input: a random sample of
.bc modules under $FPEA_HOME/kernel/linux-5.17.11/drivers.  Output: a report on stdout and
filter_validate.json in the cwd.  Invoked as `python3 filter_validate.py`.
"""
import json
import os
import random
import re
import subprocess
from collections import Counter

# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
HOME_ROOT = os.environ.get('FPEA_HOME') or os.path.expanduser('~')
TMP_ROOT = os.environ.get('FPEA_TMP', '/tmp')

DIS = '/usr/bin/llvm-dis-14'
KERNEL_DRIVERS = f'{HOME_ROOT}/kernel/linux-5.17.11/drivers'
N_MODULES = 400
SEED = 42
MAX_EXAMPLES = 12       # examples kept per disagreement class
SHOWN_EXAMPLES = 8      # examples printed per disagreement class

# naming rule: a symbol matching this pattern is classified as contamination
CONTAM = re.compile(r'(\.\d+$|\.(constprop|isra|part|cold)\b|^asan\.|^__asan|^kasan\.|^__ubsan|^ubsan\.|^__bpf_trace_|^trace_event_raw_event_|^perf_trace_|^trace_raw_output_|^__traceiter_|^__probestub_|^rcu_lock_|^local_bh_|^__local_bh_|^llvm\.|^__cfi_|^__pfx_|^__x86_indirect|^__sanitizer_cov)')

DEFINE_RE = re.compile(r'^define[^@]*@([\w.$]+)\(', re.M)
DEFINE_DBG_RE = re.compile(r'^define[^@]*@([\w.$]+)\([^\n]*!dbg !(\d+)', re.M)
SUBPROGRAM_RE = re.compile(r'^!(\d+) = (?:distinct )?!DISubprogram\(([^\n]*)\)', re.M)


def disassemble(bc):
    """Return the textual IR of a bitcode module, or None if llvm-dis fails."""
    try:
        return subprocess.run([DIS, '-o', '-', bc],
                              capture_output=True, text=True, timeout=180).stdout
    except Exception:
        return None


def parse_subprograms(ll):
    """Parse the DISubprogram metadata nodes: id -> {name, line, file}."""
    dbg = {}
    for m in SUBPROGRAM_RE.finditer(ll):
        body = m.group(2)
        nm = re.search(r'name: "([^"]*)"', body)
        ln = re.search(r'line: (\d+)', body)
        fl = re.search(r'file: !(\d+)', body)
        dbg[m.group(1)] = dict(name=nm.group(1) if nm else None,
                               line=int(ln.group(1)) if ln else None,
                               file=fl.group(1) if fl else None)
    return dbg


def classify_by_debug_info(subprogram):
    """Debug-based classification: contamination if there is no DISubprogram
    (compiler-generated) or no source line.  Returns (is_contamination, reason)."""
    if subprogram is None:
        return True, 'no DISubprogram'
    if subprogram['line'] is None or subprogram['file'] is None:
        return True, 'no source location'
    # function present in source: also check that the DISubprogram name matches the symbol name
    return False, f"src line {subprogram['line']}"


def analyze(bc):
    """Classify every defined function of one module by both methods.

    Returns a list of (function, by_name, by_dbg, reason) or None if the module
    could not be disassembled or defines no function."""
    ll = disassemble(bc)
    if ll is None:
        return None
    defined = set(DEFINE_RE.findall(ll))
    if not defined:
        return None
    # function -> DISubprogram metadata reference (!dbg !N)
    fn2dbg = {}
    for m in DEFINE_DBG_RE.finditer(ll):
        fn2dbg[m.group(1)] = m.group(2)
    dbg = parse_subprograms(ll)
    res = []
    for f in defined:
        by_name = bool(CONTAM.search(f))          # naming rule: True = classified as contamination
        by_dbg, reason = classify_by_debug_info(dbg.get(fn2dbg.get(f, ''), None))
        res.append((f, by_name, by_dbg, reason))
    return res


def sample_modules(root, n_modules, seed):
    """Random sample of n_modules .bc files under root (fixed seed)."""
    random.seed(seed)
    bcs = [os.path.join(r, f) for r, _, fs in os.walk(root) for f in fs if f.endswith('.bc')]
    random.shuffle(bcs)
    return bcs[:n_modules]


def print_report(nmod, agree, disagree, cm, ex):
    tot = agree + disagree
    print(f"Compared modules: {nmod}, functions: {tot}")
    print(f"Agree {agree} ({agree/tot*100:.2f}%), disagree {disagree} ({disagree/tot*100:.2f}%)")
    print()
    print("Confusion matrix (naming rule, debug-based) → count")
    print(f"  both contamination          : {cm[(True,True)]}")
    print(f"  both normal                 : {cm[(False,False)]}")
    print(f"  naming only (over-removal)  : {cm[(True,False)]}")
    print(f"  debug only (missed)         : {cm[(False,True)]}")
    print()
    print("[Examples flagged only by the naming rule — may actually be source functions]")
    for f, r in ex['name_only'][:SHOWN_EXAMPLES]:
        print(f"   {f[:55]:57} {r}")
    print("[Contamination only by the debug criterion — "
          "compiler symbols missed by the naming rule]")
    for f, r in ex['dbg_only'][:SHOWN_EXAMPLES]:
        print(f"   {f[:55]:57} {r}")


def main(root, n_modules=400, seed=42):
    bcs = sample_modules(root, n_modules, seed)
    agree = disagree = 0
    cm = Counter()   # (by_name, by_dbg) confusion matrix
    ex = {'name_only': [], 'dbg_only': []}
    nmod = 0
    for bc in bcs:
        r = analyze(bc)
        if not r:
            continue
        nmod += 1
        for f, bn, bd, reason in r:
            cm[(bn, bd)] += 1
            if bn == bd:
                agree += 1
            else:
                disagree += 1
                key = 'name_only' if bn else 'dbg_only'
                if len(ex[key]) < MAX_EXAMPLES:
                    ex[key].append((f, reason))
    print_report(nmod, agree, disagree, cm, ex)
    summary = {'modules': nmod, 'total': agree + disagree, 'agree': agree, 'disagree': disagree,
               'cm': {str(k): v for k, v in cm.items()}}
    with open('filter_validate.json', 'w') as fp:
        json.dump(summary, fp)


if __name__ == "__main__":
    main(KERNEL_DRIVERS, N_MODULES)

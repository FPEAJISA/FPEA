"""Link-layer (LLVM 14) measurement of the effect of adding the C5 signal (select/phi/ret flow).

Library part (imported by behavior.py, atfinal.py and decomp.py): the tool paths, the
contamination/export/symbol regexes, analyze_text(ll) / analyze(bc) and job(path), plus
list_input_files() that enumerates the linked .bc units.
Run directly (`python3 measure_c5r.py`): analyses every unit with a Pool of 14, prints the
C4-vs-C5 summary to stdout and writes c5r_result.json into the current directory.
"""
import os
import re
import subprocess
import json
import random
from multiprocessing import Pool
from collections import Counter

# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
HOME_ROOT = os.environ.get('FPEA_HOME') or os.path.expanduser('~')
TMP_ROOT = os.environ.get('FPEA_TMP', '/tmp')

# Baseline tool (original UAFX entry-point handler) and the LLVM 14 disassembler.
TOOL = f'{HOME_ROOT}/rerun/uafx_orig/entry_point_handler_orig'
DIS = f'{HOME_ROOT}/llvm/build/bin/llvm-dis'
# Linked module layer (output of build_linked.sh 14) and the matching kernel source tree.
LINKED_DIR = f'{HOME_ROOT}/linux_bc/linked-nosan14-5.17.11'
SRC_DIR = f'{HOME_ROOT}/rerun/nosan/src14/linux-5.17.11'

# Compiler/instrumentation artefacts that are never counted as defined functions.
CONTAM = re.compile(
    r'(\.(constprop|isra|part|cold)(\.\d+)?$|^asan\.|^__asan|^kasan\.|^__ubsan|^ubsan\.'
    r'|^__bpf_trace_|^trace_event_raw_event_|^perf_trace_|^trace_raw_output_|^__traceiter_'
    r'|^__probestub_|^rcu_lock_|^local_bh_|^__local_bh_|^llvm\.|^__cfi_|^__pfx_'
    r'|^__x86_indirect|^__sanitizer_cov)')
# EXPORT_SYMBOL artefacts (globals whose initialiser mentions the function but are no C1).
EXP = re.compile(r'(__UNIQUE_ID___addressable_|\._entry_ptr|\._entry\b|\._entry\.\d)')
# A @symbol reference that is not a call target (no '(' follows) and not part of a name.
SYM = re.compile(r'(?<![\w.])@([\w.$]+)(?![\w.(])')
# select/phi/ret instruction line (kept for reference; not used by the analysis below).
C5LINE = re.compile(r'^\s*(?:%[\w.$]+\s*=\s*)?(select|phi)\b|^\s*ret\b')


def analyze_text(ll):
    """Collect the FPEA signals C1..C5 from the IR text of one unit.

    Returns (c, dec, sig, c5ctx): the set of defined non-contaminated functions, the set of
    declared (external) functions, {function: {signal, ...}} and, per C5 function, one
    example IR line (truncated) showing where the select/phi/ret value escaped.
    """
    d = set(re.findall(r'^define[^@]*@([\w.$]+)\(', ll, re.M))
    c = {x for x in d if not CONTAM.search(x)}
    dec = set(re.findall(r'^declare[^@]*@([\w.$]+)\(', ll, re.M))
    sig = {}

    def add(f, s):
        sig.setdefault(f, set()).add(s)

    # C1: address used in a global initialiser (EXPORT_SYMBOL artefacts excluded).
    for g in re.finditer(r'^@([\w.$]+)\s*=[^\n]*', ll, re.M):
        if EXP.search(g.group(1)):
            continue
        for a in SYM.findall(g.group(0)):
            if a in c:
                add(a, 'C1')
    # C2: module init/exit and initcall/exitcall entries.
    for n in ('init_module', 'cleanup_module'):
        if n in c:
            add(n, 'C2')
    for m in re.finditer(r'@(__initcall__?\w*|__exitcall_\w*)\s*=[^\n]*@([\w.$]+)', ll):
        if m.group(2) in c:
            add(m.group(2), 'C2')
    # C3: address passed as a call argument (the callee itself does not count).
    for m in re.finditer(r'\bcall[^\n]*?@([\w.$]+)\(([^\n]*)\)', ll):
        for a in SYM.findall(m.group(2)):
            if a in c and a != m.group(1):
                add(a, 'C3')
    # C4: address appears in a store instruction.
    for m in re.finditer(r'\bstore\b[^\n]*?(?<![\w.])@([\w.$]+)(?![\w.(])[^\n]*', ll):
        if m.group(1) in c:
            add(m.group(1), 'C4')
    # C5: address returned, or carried by select/phi into a store / ret / call argument.
    c5ctx = {}
    c5imm = 0
    bodies = re.split(r'\n(?=define )', ll)
    for body in bodies:
        if not body.startswith('define'):
            continue
        lines = body.split('\n')
        vsyms = {}                                   # %v -> {symbols}
        for line in lines:
            m = re.match(r'^\s*(%[\w.$]+)\s*=\s*(select|phi)\b(.*)$', line)
            if m:
                ss = {a for a in SYM.findall(m.group(3)) if a in c}
                for v in re.findall(r'(%[\w.$]+)', m.group(3)):
                    ss |= vsyms.get(v, set())         # chained propagation
                if ss:
                    vsyms[m.group(1)] = ss
            mr = re.match(r'^\s*ret\b(.*)$', line)
            if mr:
                for a in SYM.findall(mr.group(1)):
                    if a in c:
                        add(a, 'C5')
                        c5ctx.setdefault(a, 'ret: ' + line.strip()[:120])
        if not vsyms:
            continue
        for line in lines:
            used = [v for v in vsyms if re.search(re.escape(v) + r'(?![\w.$])', line)]
            if not used:
                continue
            L = line.strip()
            for v in used:
                sink = None
                if re.match(r'store\b[^,]*\b' + re.escape(v) + r'(?![\w.$])\s*,', L):
                    sink = 'store'
                elif re.match(r'ret\b.*' + re.escape(v) + r'(?![\w.$])', L):
                    sink = 'ret'
                else:
                    mc = re.search(r'\bcall\b[^(]*?(%[\w.$]+|@[\w.$]+)\((.*)\)', L)
                    if mc:
                        if mc.group(1) == v:
                            c5imm += 1          # indirect call at this site — not an escape
                        elif re.search(re.escape(v) + r'(?![\w.$])', mc.group(2)):
                            sink = 'callarg'
                if sink:
                    for a in vsyms[v]:
                        add(a, 'C5')
                        c5ctx.setdefault(a, sink + ': ' + L[:120])
    return c, dec, sig, c5ctx


def analyze(bc):
    """Disassemble one .bc file with llvm-dis and analyse its IR text."""
    ll = subprocess.run([DIS, '-o', '-', bc], capture_output=True, text=True, timeout=900).stdout
    return analyze_text(ll)


def job(path):
    """Pool worker: FPEA signals of one unit plus the baseline tool's entry points.

    Returns (path, c, dec, sig, ctx, W) where W maps each baseline entry point to its
    kind (first column of the tool output), or None if the analysis raised.
    """
    try:
        c, dec, sig, ctx = analyze(path)
    except Exception:
        return None
    out = f'{TMP_ROOT}/c5_' + os.path.basename(path) + '.txt'
    subprocess.run(['timeout', '600', TOOL, path, out], capture_output=True)
    W = {}
    if os.path.exists(out):
        with open(out, errors='replace') as fh:
            for line in fh:
                parts = line.strip().split(':')
                if len(parts) >= 2:
                    W.setdefault(parts[1], parts[0])
        os.remove(out)
    return path, c, dec, sig, ctx, W


def list_input_files():
    """All linked module and builtin .bc units; for modules whose llvm-link failed
    (FAIL lines of link_report.txt) the individual .name.o.bc units are used instead."""
    files = [os.path.join(LINKED_DIR, 'modules', f)
             for f in os.listdir(LINKED_DIR + '/modules') if f.endswith('.bc')]
    files += [os.path.join(LINKED_DIR, 'builtin', f)
              for f in os.listdir(LINKED_DIR + '/builtin') if f.endswith('.bc')]
    for line in open(LINKED_DIR + '/link_report.txt'):
        if line.startswith('FAIL'):
            mod_path = os.path.join(SRC_DIR, line.split()[1])
            for obj in open(mod_path).read().split('\n')[0].split():
                unit_bc = os.path.join(SRC_DIR, os.path.dirname(obj),
                                       '.' + os.path.basename(obj) + '.bc')
                if os.path.exists(unit_bc):
                    files.append(unit_bc)
    return files


def main():
    """Measure FPEA v4 (C1~C4) vs v5 (+C5) over the link layer and compare with the baseline."""
    files = list_input_files()
    D = 0                       # defined functions
    v4 = 0                      # entry points with at least one of C1..C4
    v5 = 0                      # entry points with at least one of C1..C5
    c5only = []                 # (function, unit, context) admitted by C5 only
    sigc = Counter()            # per-signal counts (with overlap)
    Wn = I4 = I5 = 0            # baseline entry points and their intersection with v4 / v5
    miss5 = Counter()           # baseline entry points missed by v5, by (kind, status)
    rec = []                    # baseline entry points recovered by C5
    with Pool(14) as p:
        for r in p.imap_unordered(job, files, chunksize=8):
            if not r:
                continue
            path, c, dec, sig, ctx, W = r
            D += len(c)
            E4 = {f for f, s in sig.items() if s - {'C5'}}
            E5 = set(sig)
            v4 += len(E4)
            v5 += len(E5)
            for f, s in sig.items():
                for x in s:
                    sigc[x] += 1
            for f in E5 - E4:
                c5only.append((f, os.path.basename(path), ctx.get(f, '')))
            for fn, k in W.items():
                Wn += 1
                if fn in E4:
                    I4 += 1
                if fn in E5:
                    I5 += 1
                    if fn not in E4:
                        rec.append((k, fn, os.path.basename(path)))
                else:
                    status = 'defined' if fn in c else ('external' if fn in dec else 'other')
                    miss5[(k, status)] += 1
    print(f"=== Link layer LLVM14 (+fallback) — effect of adding C5 ===")
    print(f"  defined functions {D}")
    print(f"  FPEA v4 (C1~C4) : {v4}")
    print(f"  FPEA v5 (+C5)   : {v5}   (+{v5-v4}, +{(v5-v4)/v4*100:.2f}%)")
    print(f"  per signal (with overlap): {dict(sigc)}")
    print(f"  baseline {Wn}: ∩ v4={I4} → v5={I5}  (recovered by C5 {I5-I4})")
    print(f"  miss rate v4={(v4-I4)/v4*100:.2f}%  v5={(v5-I5)/v5*100:.2f}%")
    print(f"  WL\\FPEA breakdown after C5: {dict(miss5)}")
    print(f"\n  examples of baseline entry points recovered by C5:")
    for x in rec[:8]:
        print("    ", x)
    random.seed(21)
    samp = random.sample(c5only, min(40, len(c5only)))
    result = dict(defined=D, v4=v4, v5=v5, W=Wn, I4=I4, I5=I5,
                  miss5={f"{a}|{b}": n for (a, b), n in miss5.items()},
                  c5only_total=len(c5only), sample=samp)
    with open('c5r_result.json', 'w') as fh:
        json.dump(result, fh, indent=1)
    print(f"\n  functions newly added by C5 only: {len(c5only)}  (sample 40 → c5_result.json)")
    for f, m, ctxline in samp[:12]:
        print(f"    {f:38} [{m[:34]}]  {ctxline[:80]}")


if __name__ == '__main__':
    main()

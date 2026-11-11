"""False-positive audit of the link-layer FPEA entry points (LLVM 14, blockaddress fixed).

Library part (imported by fp_refine.py): the regexes, analyze(ll) which tags every piece of
evidence (C1:meta-global, C3:printk, C4:local-alloca, ...) and list_input_files().
Run directly (`python3 fp_audit.py > fp_audit.log`): counts the entry points whose evidence
consists only of suspect tags (FP candidates) and writes fp_audit.json.
"""
import os
import re
import subprocess
import json
from multiprocessing import Pool
from collections import Counter, defaultdict

# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
HOME_ROOT = os.environ.get('FPEA_HOME') or os.path.expanduser('~')
TMP_ROOT = os.environ.get('FPEA_TMP', '/tmp')

DIS = f'{HOME_ROOT}/llvm/build/bin/llvm-dis'
# Linked module layer (output of build_linked.sh 14) and the matching kernel source tree.
LINKED_DIR = f'{HOME_ROOT}/linux_bc/linked-nosan14-5.17.11'
SRC = f'{HOME_ROOT}/rerun/nosan/src14/linux-5.17.11'

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
# blockaddress(@f, %bb) operands (label addresses, not function addresses).
BA = re.compile(r'blockaddress\(@[\w.$]+,\s*%[\w.$]+\)')
# Globals that are compiler/tracing metadata rather than real tables (C1:meta-global).
GMETA = re.compile(
    r'^(llvm\.(used|compiler\.used|global_ctors|global_dtors)|__tracepoint_|__bpf_trace_tp_map_'
    r'|__event_|_ftrace_|_eil_addr_|_kbl_addr_|__UNIQUE_ID_|__SCK__|__SCT__|___ratelimit'
    r'|__func__|__kstrtab|__ksymtab|__jump_table|__bug_table)')
# Callees that only print their pointer argument (C3:printk).
PRINTK = re.compile(
    r'^(_printk|printk|vprintk\w*|_dev_(err|warn|info|notice|emerg|crit|alert)|dev_printk\w*'
    r'|__dev_printk|netdev_(err|warn|info|printk)|__netdev_printk'
    r'|__dynamic_(pr|dev|netdev|ibdev)_debug|__warn_printk|seq_printf|seq_puts|snprintf'
    r'|scnprintf|sprintf|vsnprintf|__trace_bprintk|__trace_printk|trace_\w+|panic'
    r'|_printk_deferred)$')
# Iterator-type callees that call their callback argument synchronously (C3:iterator).
ITER = re.compile(
    r'^(sort|sort_r|list_sort|bsearch|bus_for_each_\w+|driver_for_each_device'
    r'|device_for_each_child\w*|class_for_each_device|idr_for_each|klist_\w+|\w+_for_each\w*'
    r'|\w+_walk\w*|\w+_iterate\w*|iterate_\w+|walk_\w+)$')


def analyze(ll):
    """Tag every piece of FPEA evidence in the IR text of one unit.

    Returns (c, ev, ctx): defined non-contaminated functions, {function: {(signal, tag)}}
    and {(function, tag): example IR line (truncated to 150 chars)}.
    """
    ll = BA.sub('blockaddress(BA)', ll)                                   # ★ blockaddress fix
    c = {x for x in re.findall(r'^define[^@]*@([\w.$]+)\(', ll, re.M) if not CONTAM.search(x)}
    ev = defaultdict(set)        # function -> {(signal,tag)}
    ctx = {}

    def add(f, s, t, L):
        ev[f].add((s, t))
        ctx.setdefault((f, t), L[:150])

    # C1: global initialisers; metadata globals get their own tag.
    for g in re.finditer(r'^@([\w.$]+)\s*=[^\n]*', ll, re.M):
        gname = g.group(1)
        line = g.group(0)
        if EXP.search(gname):
            continue
        t = 'C1:meta-global' if GMETA.search(gname) else 'C1:normal'
        for a in SYM.findall(line):
            if a in c:
                add(a, 'C1', t, line)
    # C2: module init/exit and initcall/exitcall entries.
    for n in ('init_module', 'cleanup_module'):
        if n in c:
            add(n, 'C2', 'C2:name', '')
    for m in re.finditer(r'@(__initcall__?\w*|__exitcall_\w*)\s*=[^\n]*@([\w.$]+)', ll):
        if m.group(2) in c:
            add(m.group(2), 'C2', 'C2:initcall', m.group(0))
    # C3/C4/C5 per function body.
    for body in re.split(r'\n(?=define )', ll):
        if not body.startswith('define'):
            continue
        lines = body.split('\n')
        alloca = {m.group(1) for L in lines
                  for m in [re.match(r'\s*(%[\w.$]+)\s*=\s*alloca\b', L)] if m}
        gepbase = {}                # getelementptr result -> base pointer
        for L in lines:
            mg = re.match(r'\s*(%[\w.$]+)\s*=\s*getelementptr\b[^,]*,[^,]*?\s(%[\w.$]+)\s*,', L)
            if mg:
                gepbase[mg.group(1)] = mg.group(2)
        vsyms = {}                  # %v -> {symbols} carried by select/phi
        for L in lines:
            S = L.strip()
            mc = re.search(r'\bcall\b[^\n]*?@([\w.$]+)\(([^\n]*)\)', S)
            if mc:
                callee = mc.group(1)
                for a in SYM.findall(mc.group(2)):
                    if a in c and a != callee:
                        if callee.startswith('llvm.'):
                            t = 'C3:llvm-intrinsic'
                        elif PRINTK.match(callee):
                            t = 'C3:printk'
                        elif ITER.match(callee):
                            t = 'C3:iterator'
                        else:
                            t = 'C3:normal'
                        add(a, 'C3', t, S)
            ms = re.match(r'store\s+ptr\s+@([\w.$]+)\s*,\s*ptr\s+(%[\w.$]+)', S)
            if ms and ms.group(1) in c:
                d = ms.group(2)
                base = gepbase.get(d, d)
                t = 'C4:local-alloca' if (d in alloca or base in alloca) else 'C4:normal'
                add(ms.group(1), 'C4', t, S)
            elif S.startswith('store'):
                for a in SYM.findall(S):
                    if a in c and not re.match(r'store\s+ptr\s+@' + re.escape(a) + r'\b', S):
                        # e.g. used as the address side (a position other than the value)
                        add(a, 'C4', 'C4:other-operand', S)
            m5 = re.match(r'\s*(%[\w.$]+)\s*=\s*(select|phi)\b(.*)$', L)
            if m5:
                ss = {a for a in SYM.findall(m5.group(3)) if a in c}
                for v in re.findall(r'(%[\w.$]+)', m5.group(3)):
                    ss |= vsyms.get(v, set())
                if ss:
                    vsyms[m5.group(1)] = ss
            mr = re.match(r'\s*ret\b(.*)$', L)
            if mr:
                for a in SYM.findall(mr.group(1)):
                    if a in c:
                        add(a, 'C5', 'C5:ret', S)
        for L in lines:
            S = L.strip()
            for v, ss in vsyms.items():
                if not re.search(re.escape(v) + r'(?![\w.$])', S):
                    continue
                sink = None
                if re.match(r'store\b[^,]*\b' + re.escape(v) + r'(?![\w.$])\s*,', S):
                    sink = 'store'
                elif re.match(r'ret\b.*' + re.escape(v) + r'(?![\w.$])', S):
                    sink = 'ret'
                else:
                    mc = re.search(r'\bcall\b[^(]*?(%[\w.$]+|@[\w.$]+)\((.*)\)', S)
                    if (mc and mc.group(1) != v
                            and re.search(re.escape(v) + r'(?![\w.$])', mc.group(2))):
                        sink = 'callarg'
                if sink:
                    for a in ss:
                        add(a, 'C5', 'C5:' + sink, S)
    return c, ev, ctx


def list_input_files():
    """All linked module and builtin .bc units; for modules whose llvm-link failed
    (FAIL lines of link_report.txt) the individual .name.o.bc units are used instead."""
    files = [os.path.join(LINKED_DIR, 'modules', f)
             for f in os.listdir(LINKED_DIR + '/modules') if f.endswith('.bc')]
    files += [os.path.join(LINKED_DIR, 'builtin', f)
              for f in os.listdir(LINKED_DIR + '/builtin') if f.endswith('.bc')]
    for line in open(LINKED_DIR + '/link_report.txt'):
        if line.startswith('FAIL'):
            mod_path = os.path.join(SRC, line.split()[1])
            for obj in open(mod_path).read().split('\n')[0].split():
                unit_bc = os.path.join(SRC, os.path.dirname(obj),
                                       '.' + os.path.basename(obj) + '.bc')
                if os.path.exists(unit_bc):
                    files.append(unit_bc)
    return files


# Evidence tags regarded as suspect (an entry point carrying only these is an FP candidate).
SUSP = {'C1:meta-global', 'C3:printk', 'C3:iterator', 'C3:llvm-intrinsic', 'C4:local-alloca',
        'C4:other-operand'}


def w(p):
    """Pool worker: (unit name, defined count, [(function, tags, only-suspect?,
    {suspect tag: example line})]) for unit p, or None if llvm-dis failed."""
    try:
        ll = subprocess.run([DIS, '-o', '-', p], capture_output=True, text=True,
                            timeout=900).stdout
    except Exception:
        return None
    c, ev, ctx = analyze(ll)
    res = []
    for f, E in ev.items():
        tags = {t for _, t in E}
        onlys = tags <= SUSP
        res.append((f, tuple(sorted(tags)), onlys,
                    {t: ctx.get((f, t), '') for t in tags if t in SUSP}))
    return os.path.basename(p), len(c), res


def main():
    """Tag distribution and FP candidates over all units; writes fp_audit.json."""
    files = list_input_files()
    D = F = 0                       # defined functions / FPEA entry points
    tagany = Counter()              # tag -> number of entry points carrying it
    onlyby = Counter()              # suspect-tag combination -> number of FP candidates
    samples = defaultdict(list)
    nsusp = 0
    with Pool(14) as pl:
        for r in pl.imap_unordered(w, files, chunksize=8):
            if not r:
                continue
            m, d, res = r
            D += d
            for f, tags, only, cx in res:
                F += 1
                for t in tags:
                    tagany[t] += 1
                if only:
                    nsusp += 1
                    key = '+'.join(t for t in tags)
                    onlyby[key] += 1
                    if len(samples[key]) < 8:
                        samples[key].append((f, m[:36], list(cx.values())[0] if cx else ''))
    print(f"defined functions {D}   FPEA(blockaddress fix) {F}")
    print("\n[evidence tag distribution — number of entry points carrying each tag]")
    for t, n in sorted(tagany.items()):
        print(f"  {t:22} {n:7}  {'<-suspect' if t in SUSP else ''}")
    print(f"\n[entry points whose evidence is only suspect patterns = FP candidates] {nsusp}"
          f"  ({nsusp/F*100:.2f}%)")
    for k, n in onlyby.most_common():
        print(f"  {k:40} {n:6}")
    for k in list(onlyby)[:8]:
        print(f"\n--- {k} examples ---")
        for f, m, L in samples[k][:6]:
            print(f"   {f:32} [{m}] {L[:95]}")
    result = dict(D=D, F=F, tagany=dict(tagany), onlyby=dict(onlyby),
                  samples={k: v for k, v in samples.items()})
    with open('fp_audit.json', 'w') as fh:
        json.dump(result, fh, indent=1)


if __name__ == '__main__':
    main()

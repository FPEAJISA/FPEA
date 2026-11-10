"""Refined false-positive judgement of the link-layer FPEA entry points.

Reuses fp_audit.analyze() and its patterns; additionally decides for every C4:local-alloca
whether the alloca escapes and for every internal C3 call whether the callee uses the
parameter only as a synchronous indirect-call target. An entry point all of whose evidence
is non-escaping is counted as an FP.
Invoked as `python3 fp_refine.py > fp_refine.log` from this folder; writes fp_refine.json.
"""
import os
import re
import subprocess
import json
from multiprocessing import Pool
from collections import Counter, defaultdict

from fp_audit import DIS, SYM, BA, analyze, list_input_files   # reuse analyze() and the patterns

VAR = re.compile(r'(%[\w.$]+)')
# Evidence tags that never establish an escape on their own.
CLEAR = {'C1:meta-global', 'C3:printk', 'C3:iterator', 'C3:llvm-intrinsic', 'C4:other-operand'}


def split_args(s):
    """Split an IR argument/parameter list at top-level commas."""
    out = []
    d = 0
    cur = ''
    for ch in s:
        if ch in '([{<':
            d += 1
        elif ch in ')]}>':
            d -= 1
        if ch == ',' and d == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def refine(ll):
    """fp_audit.analyze() plus the escape judgements for one unit.

    Returns (c, ev, ctx, c3sync, alloca_escape): c3sync maps a function to
    [internal C3 uses judged synchronous, internal C3 uses]; alloca_escape maps a function
    stored into a local alloca to the set of escape verdicts of those allocas.
    """
    llb = BA.sub('blockaddress(BA)', ll)
    c, ev, ctx = analyze(ll)
    bodies = {}                 # function -> (parameter list text, body text)
    for body in re.split(r'\n(?=define )', llb):
        m = re.match(r'define[^@]*@([\w.$]+)\((.*?)\)\s*[^{]*\{', body, re.S)
        if m:
            bodies[m.group(1)] = (m.group(2), body)

    def param_sync(callee, idx):
        """True if the idx-th parameter of an internal callee is used only as an
        indirect-call target (synchronous callback)"""
        if callee not in bodies:
            return None          # external function: cannot decide
        params, body = bodies[callee]
        ps = split_args(params)
        if idx >= len(ps):
            return None
        mm = re.search(r'(%[\w.$]+)\s*$', ps[idx].strip())
        if not mm:
            return None
        v = mm.group(1)
        uses = 0
        only_call = True
        for L in body.split('\n')[1:]:
            S = L.strip()
            if not re.search(re.escape(v) + r'(?![\w.$])', S):
                continue
            uses += 1
            if (re.search(r'\bcall\b[^(]*?' + re.escape(v) + r'\(', S)
                    and not re.search(re.escape(v) + r'(?![\w.$])', S.split(v + '(', 1)[1])):
                continue
            only_call = False
        return only_call if uses else True

    # f -> [count judged synchronous, total internal C3 count]
    c3sync = defaultdict(lambda: [0, 0])
    alloca_escape = {}
    for fname, (params, body) in bodies.items():
        lines = body.split('\n')
        alloca = {m.group(1) for L in lines
                  for m in [re.match(r'\s*(%[\w.$]+)\s*=\s*alloca\b', L)] if m}
        gep = {}
        for L in lines:
            mg = re.match(r'\s*(%[\w.$]+)\s*=\s*getelementptr\b[^,]*,[^,]*?\s(%[\w.$]+)\s*,', L)
            if mg:
                gep[mg.group(1)] = mg.group(2)

        # does the alloca escape (single tokenization): escape if it appears as a call
        # argument, store value or ret
        def root(x):
            seen = 0
            while x in gep and seen < 20:
                x = gep[x]
                seen += 1
            return x

        esc = set()
        for L in lines:
            S = L.strip()
            cand = []
            mc = re.search(r'\bcall\b[^(]*?(?:%[\w.$]+|@[\w.$]+)\((.*)\)', S)
            if mc:
                cand += VAR.findall(mc.group(1))
            mst = re.match(r'store\s+ptr\s+(%[\w.$]+)\s*,', S)
            if mst:
                cand.append(mst.group(1))
            if S.startswith('ret '):
                cand += VAR.findall(S)
            for x in cand:
                r = root(x)
                if r in alloca:
                    esc.add(r)
        for L in lines:
            S = L.strip()
            ms = re.match(r'store\s+ptr\s+@([\w.$]+)\s*,\s*ptr\s+(%[\w.$]+)', S)
            if ms and ms.group(1) in c:
                d = ms.group(2)
                b = root(d)
                if b in alloca:
                    alloca_escape.setdefault(ms.group(1), set()).add(b in esc)
            mc = re.search(r'\bcall\b[^\n]*?@([\w.$]+)\(([^\n]*)\)', S)
            if mc and mc.group(1) in bodies and not mc.group(1).startswith('llvm.'):
                args = split_args(mc.group(2))
                for i, a in enumerate(args):
                    for s in SYM.findall(a):
                        if s in c and s != mc.group(1):
                            r = param_sync(mc.group(1), i)
                            c3sync[s][1] += 1
                            if r:
                                c3sync[s][0] += 1
    return c, ev, ctx, c3sync, alloca_escape


def w(p):
    """Pool worker: (unit name, [(function, tags, is-FP, non-escape tags, example line)])
    for unit p, or None if llvm-dis failed."""
    try:
        ll = subprocess.run([DIS, '-o', '-', p], capture_output=True, text=True,
                            timeout=900).stdout
    except Exception:
        return None
    c, ev, ctx, c3s, ae = refine(ll)
    out = []
    for f, E in ev.items():
        tags = {t for _, t in E}
        # whether each piece of evidence is judged 'non-escape'
        nonesc = set()
        if 'C4:local-alloca' in tags and ae.get(f) and not any(ae[f]):
            nonesc.add('C4:local-alloca')
        if ('C3:normal' in tags and c3s.get(f) and c3s[f][1] > 0
                and c3s[f][0] == c3s[f][1]):
            nonesc.add('C3:normal')
        bad = (tags & CLEAR) | nonesc
        others = tags - bad
        fp = not others          # all evidence non-escape → FP
        if 'C3:normal' in nonesc:
            example = ctx.get((f, 'C3:normal'), '')
        elif bad:
            example = ctx.get((f, sorted(bad)[0]), '')
        else:
            example = ''
        out.append((f, tuple(sorted(tags)), fp, tuple(sorted(bad)), example))
    return os.path.basename(p), out


def main():
    """Count the refined FPs over all units, print them by category, write fp_refine.json."""
    files = list_input_files()
    F = 0                           # FPEA entry points
    fpn = 0                         # refined FPs
    bycat = Counter()               # non-escape tag combination -> count
    ex = defaultdict(list)          # examples per combination
    with Pool(14) as pl:
        for r in pl.imap_unordered(w, files, chunksize=8):
            if not r:
                continue
            m, out = r
            for f, tags, fp, bad, cx in out:
                F += 1
                if fp:
                    fpn += 1
                    k = '+'.join(bad)
                    bycat[k] += 1
                    if len(ex[k]) < 6:
                        ex[k].append((f, m[:34], cx[:100]))
    print(f"FPEA (blockaddress fix) {F}")
    print(f"FPs after refined judgement (all evidence non-escape) {fpn}  ({fpn/F*100:.2f}%)")
    for k, n in bycat.most_common():
        print(f"  {k:44} {n:6}")
    for k in list(bycat):
        print(f"\n--- {k} ---")
        for f, m, cx in ex[k]:
            print(f"   {f:34} [{m}] {cx}")
    with open('fp_refine.json', 'w') as fh:
        json.dump(dict(F=F, fp=fpn, bycat=dict(bycat), ex={k: v for k, v in ex.items()}), fh,
                  indent=1)


if __name__ == '__main__':
    main()

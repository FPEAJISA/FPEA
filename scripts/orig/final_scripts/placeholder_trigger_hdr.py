"""Placeholder trigger experiment, header bisection: after which #include of spidev.c clang 14
emits %struct.file_operations / %struct.vm_operations_struct as opaque, complete, or with a
`{}` placeholder member.

For K = 1..N the first K includes of spidev.c plus a probe declaring both structs are compiled
in the restored 6.9 and 5.19.17 trees ($FPEA_HOME/rerun/nosan/src_rb) with the exact kbuild
command line.  Probe sources and .ll files are written next to this script.  Invoked as
`python3 placeholder_trigger_hdr.py > placeholder_trigger_hdr.log`.
"""
import os
import re
import subprocess

# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
HOME_ROOT = os.environ.get('FPEA_HOME') or os.path.expanduser('~')
TMP_ROOT = os.environ.get('FPEA_TMP', '/tmp')

SP = os.path.dirname(os.path.abspath(__file__))
CLANG = f'{HOME_ROOT}/llvm-14.0.7/bin/clang-14'
PROBE = ('struct file_operations; struct vm_operations_struct;\n'
         'const struct file_operations *__p1 __attribute__((used));\n'
         'const struct vm_operations_struct *__p2 __attribute__((used));\n')
INCLUDE_SCAN_LINES = 40     # includes are collected from the first lines of spidev.c
TREES = [
    (f'{HOME_ROOT}/rerun/nosan/src_rb/linux-6.9', '69'),
    (f'{HOME_ROOT}/rerun/nosan/src_rb/linux-5.19.17', '519'),
]


def cmdline(tree):
    """The kbuild compiler flags used for spidev.o, taken from .spidev.o.cmd."""
    s = open(f'{tree}/drivers/spi/.spidev.o.cmd').read().split('\n')[0]
    s = s.split(':= ', 1)[1].split(';')[0]
    s = re.sub(r'^\S+', '', s)
    s = re.sub(r'-Wp,-MMD,\S+', '', s)
    return s.replace('-c -o drivers/spi/spidev.o drivers/spi/spidev.c', '')


def split_top(s):
    """Split an LLVM struct body at top-level commas (brackets balanced)."""
    out = []
    d = 0
    cur = ''
    for ch in s:
        if ch in '({[':
            d += 1
        if ch in ')}]':
            d -= 1
        if ch == ',' and d == 0:
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def analyze(ll):
    """Return (state of file_operations, state of vm_operations_struct, emitted globals,
    defined functions).  A state is 'opaque', 'absent', 'complete' or the list of member
    indices containing a `{}` placeholder."""
    types = {m.group(1): m.group(2)
             for m in re.finditer(r'^(%[\w.]+) = type \{ (.*) \}$', ll, re.M)}
    opaque = set(re.findall(r'^(%[\w.]+) = type opaque$', ll, re.M))

    def st(k):
        if k in opaque:
            return 'opaque'
        if k not in types:
            return 'absent'
        mem = split_top(types[k])
        return [i for i, m in enumerate(mem) if '{}' in m] or 'complete'

    emitted = [m.group(1) for m in re.finditer(r'^@([\w.$]+) = (?!external)', ll, re.M)
               if not m.group(1).startswith('__p')]
    defs = re.findall(r'^define [^@]*@([\w.$]+)\(', ll, re.M)
    return st('%struct.file_operations'), st('%struct.vm_operations_struct'), emitted, defs


def run(tree, tag):
    """Compile the probe after the first K includes of spidev.c for every K and report."""
    src = open(f'{tree}/drivers/spi/spidev.c').read().split('\n')
    incs = [l for l in src[:INCLUDE_SCAN_LINES] if l.startswith('#include')]
    print(f'== {tag}: {len(incs)} includes')
    for K in range(1, len(incs) + 1):
        body = '\n'.join(incs[:K]) + '\n' + PROBE
        p = f'{SP}/h_{tag}_{K}.c'
        with open(p, 'w') as fp:
            fp.write(body)
        out = f'{SP}/h_{tag}_{K}.ll'
        cmd = f'cd {tree} && {CLANG} {cmdline(tree)} -Wno-error -S -emit-llvm -o {out} {p}'
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if r.returncode:
            print(K, incs[K-1], 'FAIL', r.stderr[-300:])
            continue
        fo, vo, em, df = analyze(open(out).read())
        print(f'{K:2} {incs[K-1]:40} fops={fo} vmops={vo} '
              f'emitted_globals={len(em)} defines={len(df)}')
        if K == len(incs):
            print('   emitted:', em[:40])
            print('   defines:', df[:40])


def main():
    for tree, tag in TREES:
        run(tree, tag)


if __name__ == '__main__':
    main()

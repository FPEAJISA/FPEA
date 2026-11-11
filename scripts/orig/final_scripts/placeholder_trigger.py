"""Placeholder trigger experiment: which struct layouts make clang 14 emit a `{}` placeholder
member in %struct.file_operations / %struct.vm_operations_struct of drivers/spi/spidev.c.

Recompiles variants of spidev.c (as is, with one forced struct layout, with the forced layout
at successive positions) in the restored 5.19.17 and 6.9 trees ($FPEA_HOME/rerun/nosan/src_rb)
with the exact kbuild command line and reports the placeholder member indices per variant.
Variant sources and .ll files are written next to this script.  Invoked as
`python3 placeholder_trigger.py > placeholder_trigger.log`.
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
T69 = f'{HOME_ROOT}/rerun/nosan/src_rb/linux-6.9'
T519 = f'{HOME_ROOT}/rerun/nosan/src_rb/linux-5.19.17'
# forced-layout variants are inserted after this include line
INC = r'^#include <linux/uaccess.h>'
FOPS = '%struct.file_operations'
VMOPS = '%struct.vm_operations_struct'

# (variant suffix, struct whose layout is forced, extra include needed for it)
FORCE_VARIANTS = [
    ('file',         'struct file',             None),
    ('vma',          'struct vm_area_struct',   None),
    ('vmfault',      'struct vm_fault',         None),
    ('mm',           'struct mm_struct',        None),
    ('page',         'struct page',             None),
    ('pgmap_ops',    'struct dev_pagemap_ops',  '#include <linux/memremap.h>'),
    ('device',       'struct device',           None),
    ('kernel_param', 'struct kernel_param',     None),
    ('module',       'struct module',           None),
]
# root bisection: force struct file layout at successive top-level positions
# (variant suffix, pattern of the anchor line)
POSITION_VARIANTS = [
    ('before_param',        r'^module_param\(bufsiz'),
    ('after_param',         r'^MODULE_PARM_DESC\(bufsiz'),
    ('after_sync_unlocked', r'^spidev_sync_unlocked\('),
    ('after_sync',          r'^spidev_sync\('),
    ('after_sync_read',     r'^spidev_sync_read\('),
]
POSITION_LINE = 'struct file *__fl_pos __attribute__((used)) = 0;'


def cmdline(tree):
    """The kbuild compiler flags used for spidev.o, taken from .spidev.o.cmd."""
    s = open(f'{tree}/drivers/spi/.spidev.o.cmd').read().split('\n')[0]
    s = s.split(':= ', 1)[1].split(';')[0]
    s = re.sub(r'^\S+', '', s)            # drop wllvm
    s = re.sub(r'-Wp,-MMD,\S+', '', s)
    s = s.replace('-c -o drivers/spi/spidev.o drivers/spi/spidev.c', '')
    return s


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
    """{type name -> member indices containing a `{}` placeholder} for the named struct types."""
    types = {m.group(1): m.group(2)
             for m in re.finditer(r'^(%[\w.]+) = type \{ (.*) \}$', ll, re.M)}
    res = {}
    for k, v in types.items():
        if '{}' in v:
            mem = split_top(v)
            res[k] = [i for i, m in enumerate(mem) if '{}' in m]
    return res


def compile_ll(tree, src, out):
    """Compile src to LLVM IR text (file `out`) inside `tree`; return the IR or None."""
    cmd = f'cd {tree} && {CLANG} {cmdline(tree)} -Wno-error -S -emit-llvm -o {out} {src}'
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if r.returncode:
        print('  COMPILE FAIL', r.stderr[-800:])
        return None
    return open(out).read()


def read_spidev(tree):
    return open(f'{tree}/drivers/spi/spidev.c').read().split('\n')


def write_variant(path, lines):
    with open(path, 'w') as fp:
        fp.write('\n'.join(lines))


def variant(tree, name, insert_after_pat, line, extra_include=None):
    """Compile spidev.c with `line` inserted after the last line matching insert_after_pat
    (no insertion if the pattern is None) and report the placeholder indices."""
    src = read_spidev(tree)
    if insert_after_pat is None:
        idx = None
    else:
        idx = max(i for i, l in enumerate(src) if re.search(insert_after_pat, l))
    new = list(src)
    if idx is not None:
        new.insert(idx + 1, line)
    if extra_include:
        last_include = max(i for i, l in enumerate(new) if l.startswith('#include'))
        new.insert(last_include + 1, extra_include)
    p = f'{SP}/{name}.c'
    write_variant(p, new)
    ll = compile_ll(tree, p, f'{SP}/{name}.ll')
    if ll is None:
        return
    r = analyze(ll)
    fo = r.get(FOPS)
    vo = r.get(VMOPS)
    others = sorted(k for k in r if k not in (FOPS, VMOPS))
    print(f'{name:28} fops={fo} vmops={vo} others={others}')


def position_variant(tree, nm, pat):
    """Insert the forced struct file layout at the top-level position anchored by `pat`:
    before the matched line for 'before_param', right after it for 'after_param', else after
    the closing brace of the function (approximated by the NEXT 'static' line)."""
    src = read_spidev(tree)
    i = max(k for k, l in enumerate(src) if re.search(pat, l))
    if nm == 'before_param':
        pos = i
    elif nm == 'after_param':
        pos = i + 1
    else:
        pos = next(k for k in range(i + 1, len(src)) if src[k].startswith('static '))
    new = list(src)
    new.insert(pos, POSITION_LINE)
    p = f'{SP}/v69_pos_{nm}.c'
    write_variant(p, new)
    ll = compile_ll(tree, p, f'{SP}/v69_pos_{nm}.ll')
    if ll:
        r = analyze(ll)
        print(f'{"v69_pos_"+nm:28} (line {pos+1}) fops={r.get(FOPS)} vmops={r.get(VMOPS)}')


def main():
    variant(T519, 'v519_asis', None, '')
    variant(T69, 'v69_asis', None, '')
    for nm, ty, inc in FORCE_VARIANTS:
        variant(T69, f'v69_force_{nm}', INC, f'{ty} *__fl_{nm} __attribute__((used)) = 0;', inc)
    for nm, pat in POSITION_VARIANTS:
        position_variant(T69, nm, pat)


if __name__ == '__main__':
    main()

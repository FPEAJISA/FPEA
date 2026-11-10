#!/usr/bin/env python3
"""Handler field offsets of op-table structs, parsed from the kernel source headers.

Parses the member lists of 20 op-table structs directly from the headers of four
kernel versions (5.17, 5.19, 6.9, 7.1) and measures how the field index of key
handlers shifts across versions.  Based on source definitions rather than IR
guesses, so it is exact.  Output: a report on stdout and handler_offset.json in
the cwd (read by semantic_hit.py).  Invoked as `python3 handler_offset.py`.
"""
import json
import os
import re

SRC = {
    '5.17': os.path.expanduser('~/kernel/linux-5.17.11'),
    '5.19': os.path.expanduser('~/kbuild/src/linux-5.19.17'),
    '6.9': os.path.expanduser('~/kbuild/src/linux-6.9'),
    '7.1': os.path.expanduser('~/linux-7.1.4'),
}
VERSIONS = ('5.17', '5.19', '6.9', '7.1')

# (struct, candidate defining headers)
TARGETS = [
    ('file_operations',          ['include/linux/fs.h']),
    ('net_device_ops',           ['include/linux/netdevice.h']),
    ('tty_operations',           ['include/linux/tty_driver.h']),
    ('block_device_operations',  ['include/linux/blkdev.h']),
    ('ethtool_ops',              ['include/linux/ethtool.h']),
    ('platform_driver',          ['include/linux/platform_device.h']),
    ('pci_driver',               ['include/linux/pci.h']),
    ('usb_driver',               ['include/linux/usb.h']),
    ('i2c_driver',               ['include/linux/i2c.h']),
    ('device_driver',            ['include/linux/device/driver.h', 'include/linux/device.h']),
    ('proto_ops',                ['include/linux/net.h']),
    ('inode_operations',         ['include/linux/fs.h']),
    ('watchdog_ops',             ['include/linux/watchdog.h']),
    ('iio_info',                 ['include/linux/iio/iio.h']),
    ('hid_driver',               ['include/linux/hid.h']),
    ('rtc_class_ops',            ['include/linux/rtc.h']),
    ('dev_pm_ops',               ['include/linux/pm.h']),
    ('seq_operations',           ['include/linux/seq_file.h']),
    ('v4l2_ioctl_ops',           ['include/media/v4l2-ioctl.h']),
    ('snd_pcm_ops',              ['include/sound/pcm.h']),
]

# handlers whose field index is tracked across versions
HANDLERS = ['unlocked_ioctl', 'compat_ioctl', 'read', 'write', 'open', 'release',
            'probe', 'remove', 'ndo_open', 'ndo_stop', 'ndo_start_xmit',
            'suspend', 'resume', 'shutdown', 'ioctl', 'llseek', 'mmap']


def struct_body(txt, name):
    """Return the text between the braces of `struct <name> {...}` (brace balanced),
    or None if the struct is not defined in txt."""
    m = re.search(r'struct\s+' + re.escape(name) + r'\s*\{', txt)
    if not m:
        return None
    # extract the body by brace balancing
    i = m.end()
    depth = 1
    body = ''
    while i < len(txt) and depth > 0:
        c = txt[i]
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
        if depth > 0:
            body += c
        i += 1
    return body


def split_members(body):
    """Split a struct body into member declarations at top-level ';'."""
    members = []
    depth = 0
    cur = ''
    for c in body:
        if c in '({[':
            depth += 1
        elif c in ')}]':
            depth -= 1
        if c == ';' and depth == 0:
            members.append(cur.strip())
            cur = ''
        else:
            cur += c
    return members


def member_name(mem):
    """Member name of one declaration: function pointer `(*name)(...)` or plain `type name`."""
    fp = re.search(r'\(\s*\*\s*(\w+)\s*\)\s*\(', mem)
    if fp:
        return fp.group(1)
    nm = re.findall(r'(\w+)\s*(?:\[[^\]]*\])?\s*$', mem)
    return nm[0] if nm else '?'


def parse_struct(root, name, headers):
    """Find the struct definition in the header and return the member names in order"""
    for h in headers:
        p = os.path.join(root, h)
        if not os.path.isfile(p):
            continue
        try:
            txt = open(p, errors='replace').read()
        except Exception:
            continue
        body = struct_body(txt, name)
        if body is None:
            continue
        # strip comments / preprocessor lines
        body = re.sub(r'/\*.*?\*/', '', body, flags=re.S)
        body = re.sub(r'//[^\n]*', '', body)
        body = re.sub(r'^\s*#[^\n]*$', '', body, flags=re.M)
        out = []
        for mem in split_members(body):
            if not mem.strip():
                continue
            out.append(member_name(mem))
        return out
    return None


def parse_all():
    """struct name -> {version -> member list (or None if not found)}."""
    res = {}
    for name, hs in TARGETS:
        per = {}
        for ver, root in SRC.items():
            per[ver] = parse_struct(root, name, hs)
        res[name] = per
    return res


def print_member_counts(res):
    print("=== Member count per struct (from source headers) ===")
    print(f"{'struct':28}{'5.17':>7}{'5.19':>7}{'6.9':>7}{'7.1':>7}")
    for name, per in res.items():
        row = [len(per[v]) if per[v] else 0 for v in VERSIONS]
        print(f"  {name[:26]:26}{row[0]:7d}{row[1]:7d}{row[2]:7d}{row[3]:7d}")


def print_offset_shift(res):
    print("\n=== Field offset shift of key handlers ===")
    print(f"{'struct.handler':40}{'5.17':>7}{'5.19':>7}{'6.9':>7}{'7.1':>7}  shift")
    moved = 0
    stable = 0
    rows = []
    for name, per in res.items():
        if not all(per[v] for v in per):
            continue
        for h in HANDLERS:
            idx = {}
            for v, mem in per.items():
                idx[v] = mem.index(h) if h in mem else None
            vals = [idx[v] for v in VERSIONS]
            if any(x is None for x in vals):
                continue
            tag = 'shift' if len(set(vals)) > 1 else '-'
            if tag == 'shift':
                moved += 1
            else:
                stable += 1
            rows.append((f"{name}.{h}", vals, tag))
    for k, v, t in sorted(rows, key=lambda r: (r[2] != 'shift', r[0])):
        print(f"  {k[:38]:38}{v[0]:7d}{v[1]:7d}{v[2]:7d}{v[3]:7d}  {t}")
    print(f"\nOf {moved+stable} tracked handlers, {moved} shifted offset "
          f"({moved/max(moved+stable,1)*100:.0f}%), {stable} fixed")


def main():
    res = parse_all()
    print_member_counts(res)
    print_offset_shift(res)
    out = {k: {v: (m if m else []) for v, m in p.items()} for k, p in res.items()}
    with open('handler_offset.json', 'w') as fp:
        json.dump(out, fp, indent=1)


if __name__ == '__main__':
    main()

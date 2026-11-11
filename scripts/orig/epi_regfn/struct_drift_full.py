#!/usr/bin/env python3
"""Cross-version layout drift of kernel op-table structs (tool-independent, a kernel-side fact).

For each of four kernel versions the field count of every target struct is read from the
LLVM type definitions of the first drivers/ modules that define it ($FPEA_HOME/linux_bc/linux-<ver>-full).
Inputs: $FPEA_HOME/epi_regfn/uafx_kernel_sts.json (UAFX rule structs) and the .bc trees.
Output: a report on stdout and struct_drift_full.json in the cwd.
Invoked as `python3 struct_drift_full.py`.
"""
import json
import os
import re
import subprocess

# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
HOME_ROOT = os.environ.get('FPEA_HOME') or os.path.expanduser('~')
TMP_ROOT = os.environ.get('FPEA_TMP', '/tmp')

DIS = f'{HOME_ROOT}/llvm/build/bin/llvm-dis'
KS = json.load(open(f'{HOME_ROOT}/epi_regfn/uafx_kernel_sts.json'))
# UAFX rule structs plus well-known op tables
TARGETS = sorted({st for st, _, _ in KS} | {
    'struct.ieee80211_ops', 'struct.ethtool_ops', 'struct.dev_pm_ops',
    'struct.platform_driver', 'struct.pci_driver', 'struct.usb_driver',
    'struct.i2c_driver', 'struct.spi_driver', 'struct.net_device_ops',
    'struct.tty_operations', 'struct.block_device_operations',
    'struct.v4l2_ioctl_ops', 'struct.snd_pcm_ops', 'struct.iio_info',
    'struct.device_driver', 'struct.proto_ops', 'struct.seq_operations',
    'struct.dsa_switch_ops', 'struct.ib_device_ops', 'struct.mmc_host_ops',
    'struct.drm_driver', 'struct.hid_driver', 'struct.watchdog_ops',
    'struct.rtc_class_ops', 'struct.phy_ops',
})
VERSIONS = ('5.17', '5.19', '6.9', '7.1')
# drivers/ subsystems scanned, in this order, until every target struct has been seen
SUBDIRS = ['net', 'media', 'usb', 'scsi', 'input', 'mtd', 'char', 'tty', 'hwmon',
           'misc', 'gpu', 'iio', 'watchdog', 'crypto', 'infiniband', 'hid', 'block']
TYPE_DEF_RE = re.compile(r'^%(struct\.[\w.]+) = type \{(.*)\}$', re.M)
MAX_UNCHANGED_SHOWN = 12


def split_top(body):
    """Split an LLVM struct body at top-level commas (brackets balanced)."""
    d = 0
    cur = ''
    out = []
    for ch in body:
        if ch in '{[(<':
            d += 1
        elif ch in '}])>':
            d -= 1
        if ch == ',' and d == 0:
            out.append(cur.strip())
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def scan(ver, cap=250):
    """Field count of each target struct in version `ver`: {struct -> field count}.

    At most `cap` modules per subsystem are disassembled; scanning stops as soon as
    every target has been observed."""
    root = f'{HOME_ROOT}/linux_bc/linux-{ver}-full/drivers'
    sizes = {}
    for sub in SUBDIRS:
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            continue
        bcs = [os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs if f.endswith('.bc')][:cap]
        for bc in bcs:
            if len(sizes) >= len(TARGETS):
                break
            try:
                ll = subprocess.run([DIS, '-o', '-', bc],
                                    capture_output=True, text=True, timeout=90).stdout
            except Exception:
                continue
            for m in TYPE_DEF_RE.finditer(ll):
                st = m.group(1)
                if st in TARGETS and st not in sizes:
                    sizes[st] = len(split_top(m.group(2)))
        if len(sizes) >= len(TARGETS):
            break
    return sizes


def scan_all_versions():
    out = {}
    for ver in VERSIONS:
        s = scan(ver)
        out[ver] = s
        print(f"{ver}: observed {len(s)}/{len(TARGETS)}", flush=True)
    return out


def print_drift(out):
    """Report the structs observed in all 4 versions whose field count changed."""
    common = set(out['5.17']) & set(out['5.19']) & set(out['6.9']) & set(out['7.1'])
    changed = []
    same = []
    for st in sorted(common):
        v = [out[x][st] for x in VERSIONS]
        (changed if len(set(v)) > 1 else same).append((st, v))
    print(f"\n=== Observed in all 4 versions: {len(common)} ===")
    print(f"Field count changed: {len(changed)} ({len(changed)/max(len(common),1)*100:.0f}%)")
    print(f"{'struct':36}{'5.17':>7}{'5.19':>7}{'6.9':>7}{'7.1':>7}{'delta':>7}")
    for st, v in sorted(changed, key=lambda x: -(x[1][3] - x[1][0])):
        print(f"  {st[7:][:34]:34}{v[0]:7d}{v[1]:7d}{v[2]:7d}{v[3]:7d}{v[3]-v[0]:+7d}")
    print(f"\nUnchanged: {len(same)}")
    for st, v in same[:MAX_UNCHANGED_SHOWN]:
        print(f"  {st[7:][:34]:34}{v[0]:7d}")


def main():
    out = scan_all_versions()
    with open('struct_drift_full.json', 'w') as fp:
        json.dump(out, fp, indent=1)
    print_drift(out)


if __name__ == '__main__':
    main()

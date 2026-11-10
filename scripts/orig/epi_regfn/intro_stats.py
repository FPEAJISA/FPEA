#!/usr/bin/env python3
"""Re-measurement of the introduction statistics, with explicit measurement
definitions so they are reproducible.

Each statistic is one grep over the 5.17.11 kernel source tree (~/kernel/linux-5.17.11).
Output: the counts as JSON on stdout and in intro_stats.json in the cwd.
Invoked as `python3 intro_stats.py`.
"""
import json
import os
import subprocess

S = os.path.expanduser('~/kernel/linux-5.17.11')


def sh(cmd):
    """Run a shell command and return its stripped stdout."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                          timeout=900).stdout.strip()


def count(cmd):
    """Integer result of a counting shell command (0 if it printed nothing)."""
    return int(sh(cmd) or 0)


def measure():
    """Measure every statistic in the order of the paper's introduction."""
    res = {}
    # (1) syscall: number of entries in the x86_64 syscall table (common/64 ABI)
    res['syscalls'] = count(
        f"grep -cE '^[0-9]+\\s+(common|64)\\s' {S}/arch/x86/entry/syscalls/syscall_64.tbl")
    # (2) ioctl command definitions: constants defined with the _IO/_IOR/_IOW/_IOWR macros
    #     in uapi headers
    res['ioctl_uapi'] = count(
        f"grep -rhcE '#define\\s+\\w+\\s+_IO(R|W|WR)?\\s*\\(' {S}/include/uapi --include=*.h"
        " | paste -sd+ | bc")
    # (3) all headers including drivers
    res['ioctl_all'] = count(
        f"grep -rhoE '#define\\s+\\w+\\s+_IO(R|W|WR)?\\s*\\(' {S}/include {S}/drivers --include=*.h"
        " | wc -l")
    # (4) global file_operations definitions (initializer form)
    res['fops_def'] = count(
        f"grep -rhoE 'struct\\s+file_operations\\s+\\w+\\s*=' {S} --include=*.c | wc -l")
    # (5) all global *_operations definitions
    res['ops_def'] = count(
        f"grep -rhoE 'struct\\s+\\w+_operations\\s+\\w+\\s*=' {S} --include=*.c | wc -l")
    # (6) network: proto_register + dev_add_pack calls (protocol handler registration)
    res['net_proto'] = count(
        f"grep -rhoE '(proto_register|dev_add_pack)\\s*\\(' {S}/net {S}/drivers --include=*.c"
        " | wc -l")
    # (7) module_init/module_exit in drivers (module lifecycle entry points)
    res['module_init'] = count(
        f"grep -rhoE '^module_init\\s*\\(' {S}/drivers --include=*.c | wc -l")
    res['module_exit'] = count(
        f"grep -rhoE '^module_exit\\s*\\(' {S}/drivers --include=*.c | wc -l")
    # (8) IRQ handler registration calls
    res['request_irq'] = count(
        f"grep -rhoE '(devm_)?request(_threaded)?_irq\\s*\\(' {S}/drivers --include=*.c | wc -l")
    return res


def main():
    res = measure()
    print(json.dumps(res, indent=1))
    with open('intro_stats.json', 'w') as fp:
        json.dump(res, fp, indent=1)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Prepare a new machine (Ubuntu 22.04) for a full reproduction of the FPEA paper (starting from the kernel builds). Uses only the standard library.

  python3 scripts/setup.py check          only check specs, network and sudo
  python3 scripts/setup.py all            check → apt → llvm16 → llvm14 → wllvm → kernels → layout → verify-setup
  python3 scripts/setup.py <step> ...     individual steps. Every step is safe to re-run (skips what already exists)
  options: --dry-run (print commands only) --work DIR (work folder, default ~/fpea_work) --tmp-root DIR (for testing, default /tmp)
        --force (disable the measurement-server protection) --no-sudo (skip the apt step) --quiet

Taken from releases (not built):
  clang 14.0.0      Ubuntu 22.04 packages clang-14/llvm-14 (the same packages used for the typed-IR kernel builds and for running the UAFX tool)
  clang 16.0.6      apt.llvm.org jammy llvm-toolchain-16 (1:16.0.6~++…+7cbf1a259152 — the same commit 7cbf1a2591520c2491aa35339f227775f4d3adf6 that the measurement server built from source)
  clang 14.0.6      llvm-project GitHub release tarball clang+llvm-14.0.6-x86_64-linux-gnu-rhel-8.4 (for the placeholder recompilation experiment; kept under the folder name ~/llvm-14.0.7 as on the measurement server)
  kernel sources    the 4 kernel.org cdn tarballs (sha256 pinned)
  wllvm 1.3.1       pip --user
To be installed: kernel build tools (apt), python3-matplotlib/numpy (figures), llvm-14-dev/llvm-16-dev (fpea14/fpea16 build)
"""
# NOTE: the module docstring above is printed verbatim by `--help` (argparse description);
# its long lines are kept as they are so that the help text does not change.
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request

# ---------------------------------------------------------------- constants
R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # repro folder
HOME = os.path.expanduser('~')
# session scratchpad that the original scripts use as a fixed path
SCRATCH = '/tmp/claude-1000/-home-user-fpea-gt/beb7f00d-7da4-4363-8809-fde4eb5531af/scratchpad'

# kernel version: (kernel.org path, sha256)
KERNELS = {
    '5.17.11': ('v5.x', '5708e656fae734c3a7b27718345b29e2f7bfd06dfb85acdffca0ba4505f81b31'),
    '5.19.17': ('v5.x', 'c93bb384a97ad1f0a4f18e442ce0291242722f78023eca658b22344541f09489'),
    '6.9':     ('v6.x', '24fa01fb989c7a3e28453f117799168713766e119c5381dac30115f18f268149'),
    '7.1.4':   ('v7.x', '1c63922a119675d38e3ae0f8f6ee07f15c41a786ab9ed66563749bb8c9a08e2e'),
}

# version pins
LLVM14_REL = (
    'https://github.com/llvm/llvm-project/releases/download/llvmorg-14.0.6/'
    'clang+llvm-14.0.6-x86_64-linux-gnu-rhel-8.4.tar.xz',
    '7412026be8bb8f6b4c25ef58c7a1f78ed5ea039d94f0fa633a386de9c60a6942',
)
LLVM16_COMMIT = '7cbf1a2591520c2491aa35339f227775f4d3adf6'
WLLVM_PIN = 'wllvm==1.3.1'
APT_LLVM_SH = 'https://apt.llvm.org/llvm.sh'

# apt packages
APT_BASE = [
    'build-essential', 'make', 'flex', 'bison', 'bc', 'libelf-dev', 'libssl-dev', 'dwarves',
    'cpio', 'rsync', 'kmod', 'libncurses-dev', 'pkg-config', 'zstd', 'lz4', 'xz-utils', 'wget',
    'curl', 'git', 'python3', 'python3-pip', 'python3-matplotlib', 'python3-numpy', 'clang-14',
    'llvm-14', 'llvm-14-dev', 'lld-14', 'gnupg', 'lsb-release', 'software-properties-common',
]
APT_16 = ['clang-16', 'llvm-16', 'llvm-16-dev', 'lld-16']

# toolchain and layout paths (as on the measurement server)
LLVM16_SYS = '/usr/lib/llvm-16'                    # apt.llvm.org package
LLVM16_LINK = f'{HOME}/llvm/build'                  # symlink → LLVM16_SYS (original scripts)
LLVM14_SYS_CLANG = '/usr/lib/llvm-14/bin/clang'     # Ubuntu package
LLVM14_DIR = f'{HOME}/llvm-14.0.7'                  # clang+llvm-14.0.6 release tarball
WLLVM_BIN = f'{HOME}/.local/bin/wllvm'
TARBALL_DIR = f'{HOME}/rerun/src'
LAYOUT_MARKER = f'{HOME}/rerun/nosan/build_14.log'  # exists only on the measurement server

# machine requirements (step_check / step_verify_setup)
MIN_CPU = 8
MIN_MEM_GB = 15
MIN_DISK_GB = 70
RECOMMENDED_DISK_GB = 100

args = None   # parsed CLI options (set by main)

# the llvm-14.0.7 lib added by the measurement server's ~/.profile kills Ubuntu clang-14
# (see env.sh), so clear it here too
os.environ.pop('LD_LIBRARY_PATH', None)
os.environ['PATH'] = ':'.join(
    p for p in os.environ.get('PATH', '').split(':') if 'llvm-14.0.7' not in p)


# ---------------------------------------------------------------- helpers
def log(*a):
    """Progress message on stdout (suppressed by --quiet)."""
    if not args.quiet:
        print('[setup]', *a, flush=True)


def warn(*a):
    print('[setup] warning:', *a, file=sys.stderr, flush=True)


def die(*a):
    print('[setup] abort:', *a, file=sys.stderr, flush=True)
    sys.exit(1)


def run(cmd, sudo=False, check=True, **kw):
    """Log and run a command; with --dry-run only log it and return a successful result."""
    if sudo:
        cmd = ['sudo'] + cmd
    log('$', ' '.join(cmd))
    if args.dry_run:
        return subprocess.CompletedProcess(cmd, 0, '', '')
    return subprocess.run(cmd, check=check, text=True, **kw)


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def download(url, dst, sha=None):
    """Download url to dst (skipped when dst exists with the expected sha256)."""
    if os.path.exists(dst) and (sha is None or sha256(dst) == sha):
        log('present', dst)
        return
    log('download', url, '→', dst)
    if args.dry_run:
        return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tmp = dst + '.part'

    def hook(n, bs, total):
        if total > 0 and n % 200 == 0:
            print(f'\r   {n*bs/2**20:7.1f} / {total/2**20:.1f} MB', end='', file=sys.stderr,
                  flush=True)

    urllib.request.urlretrieve(url, tmp, hook)
    print(file=sys.stderr)
    if sha and sha256(tmp) != sha:
        os.remove(tmp)
        die('sha256 mismatch', url)
    os.replace(tmp, dst)


def symlink(target, link):
    """link → target. Pass if the same link already exists, replace a different link,
    preserve a real file/folder (warning)."""
    if os.path.islink(link):
        if os.readlink(link) == target:
            return
        log('relink', link, '→', target)
        if not args.dry_run:
            os.remove(link)
    elif os.path.exists(link):
        warn('already a real file/folder, not creating a link:', link)
        return
    log('link', link, '→', target)
    if not args.dry_run:
        os.makedirs(os.path.dirname(link), exist_ok=True)
        os.symlink(target, link)


def copy_tree(src, dst, only=None):
    """Copy the regular files of src (optionally only the names in `only`) into dst.
    Subfolders are skipped; a file whose size and sha256 already match is left alone."""
    if not args.dry_run:
        os.makedirs(dst, exist_ok=True)
    n = 0
    for f in sorted(os.listdir(src)):
        if only and f not in only:
            continue
        s = os.path.join(src, f)
        d = os.path.join(dst, f)
        if os.path.isdir(s):
            continue
        same_size = os.path.exists(d) and os.path.getsize(d) == os.path.getsize(s)
        if same_size and sha256(d) == sha256(s):
            continue
        if not args.dry_run:
            shutil.copy2(s, d)
        n += 1
    log(f'copy {src} → {dst} ({n} files updated)')


def scratch_link():
    """The fixed scratchpad path of the original scripts, relocated under --tmp-root."""
    tmp_root = args.tmp_root
    if tmp_root == '/tmp':
        return SCRATCH
    return tmp_root + SCRATCH[len('/tmp'):]


# ---------------------------------------------------------------- steps
def step_check():
    """Print the machine specs, network reachability and sudo state as JSON; warn on shortfalls."""
    info = {}
    try:
        info['os'] = [l.split('=', 1)[1].strip('"\n')
                      for l in open('/etc/os-release') if l.startswith('PRETTY_NAME')][0]
    except Exception:
        info['os'] = platform.platform()
    info['cpu'] = os.cpu_count()
    mem = [l for l in open('/proc/meminfo') if l.startswith('MemTotal')][0].split()[1]
    info['mem_gb'] = round(int(mem) / 2**20, 1)
    st = shutil.disk_usage(HOME)
    info['disk_free_gb'] = round(st.free / 2**30, 1)
    info['python'] = platform.python_version()
    info['sudo'] = subprocess.run(['sudo', '-n', 'true'], capture_output=True).returncode == 0

    def head(url):
        try:
            req = urllib.request.Request(url, method='HEAD')
            urllib.request.urlopen(req, timeout=15)
            return True
        except Exception:
            return False

    info['net_kernel_org'] = head(
        'https://cdn.kernel.org/pub/linux/kernel/v5.x/linux-5.17.11.tar.xz')
    info['net_github'] = head(LLVM14_REL[0])
    info['net_apt_llvm'] = head(APT_LLVM_SH)
    print(json.dumps(info, ensure_ascii=False, indent=1))
    if 'Ubuntu 22.04' not in info['os']:
        warn('Not Ubuntu 22.04. clang-14 1:14.0.0-1ubuntu1.1 is a 22.04 (jammy) package. '
             'llvm-toolchain-*-14 from apt.llvm.org can substitute, '
             'but it is not the same package build.')
    if info['cpu'] < MIN_CPU:
        warn('fewer than 8 cores — the 6 kernel builds will take more than 10 hours')
    if info['mem_gb'] < MIN_MEM_GB:
        warn('less than 16 GB of memory — reduce -j (env.sh FPEA_NPROC)')
    if info['disk_free_gb'] < MIN_DISK_GB:
        die(f'free disk {info["disk_free_gb"]} GB — at least 70 GB (100 GB recommended) needed: '
            f'6 build trees 25 + debug build 22 + bitcode 5.5 + toolchains 7 + '
            f'source tarballs 0.5 + outputs 2')
    if info['disk_free_gb'] < RECOMMENDED_DISK_GB:
        warn(f'free disk {info["disk_free_gb"]} GB — 100 GB or more recommended')
    if not info['sudo'] and not args.no_sudo:
        warn('no passwordless sudo. Authenticate with `sudo -v` before the apt step, '
             'or skip apt with --no-sudo and install the packages yourself')
    if not all(info[k] for k in ('net_kernel_org', 'net_github', 'net_apt_llvm')):
        warn('some sites are not reachable — download those files by hand and place them '
             'at the same paths; they are then skipped')
    return info


def step_apt():
    """Install the build packages and LLVM 16 from apt.llvm.org (needs sudo)."""
    if args.no_sudo:
        log('--no-sudo: skipping apt. Required packages:', ' '.join(APT_BASE + APT_16))
        return
    env = dict(os.environ, DEBIAN_FRONTEND='noninteractive')
    run(['apt-get', 'update'], sudo=True, env=env)
    run(['apt-get', 'install', '-y'] + APT_BASE, sudo=True, env=env)
    # LLVM 16 from apt.llvm.org (jammy: 1:16.0.6~++20231112…+7cbf1a259152)
    sh = os.path.join(R, 'logs', 'llvm.sh')
    os.makedirs(os.path.dirname(sh), exist_ok=True)
    download(APT_LLVM_SH, sh)
    run(['bash', sh, '16'], sudo=True, env=env)
    run(['apt-get', 'install', '-y'] + APT_16, sudo=True, env=env)


def step_llvm16():
    """~/llvm/build → /usr/lib/llvm-16 (the original scripts use
    $HOME/llvm/build/bin/{clang,clang++,llvm-config,llvm-dis,llvm-link})"""
    tgt = LLVM16_SYS
    if not os.path.isdir(tgt) and not args.dry_run:
        die(tgt, 'missing — run the apt step first')
    if not args.dry_run:
        os.makedirs(f'{HOME}/llvm', exist_ok=True)
    symlink(tgt, LLVM16_LINK)
    if not args.dry_run:
        v = subprocess.run([f'{LLVM16_LINK}/bin/clang', '--version'],
                           capture_output=True, text=True).stdout
        log('clang16:', v.split('\n')[0])
        if '16.0.6' not in v:
            warn('not clang 16.0.6:', v.split('\n')[0])
        if LLVM16_COMMIT[:12] not in v:
            warn(f'not the same commit as the measurement server ({LLVM16_COMMIT[:12]}) '
                 f'— the IR may differ')
        for t in ('llvm-config', 'llvm-dis', 'llvm-link', 'clang++'):
            if not os.path.exists(f'{LLVM16_LINK}/bin/{t}'):
                warn('missing:', f'{LLVM16_LINK}/bin/{t}', '(check that llvm-16-dev is installed)')


def step_llvm14():
    """clang+llvm-14.0.6 release → ~/llvm-14.0.7 (folder name as on the measurement server;
    placeholder_trigger*.py and tca_pilot.py use this path)"""
    d = LLVM14_DIR
    url, sha = LLVM14_REL
    tb = os.path.join(d, os.path.basename(url))
    if os.path.exists(f'{d}/bin/clang-14'):
        log('present', d)
        return
    download(url, tb, sha)
    log('extract', tb, '→', d)
    if args.dry_run:
        return
    # extract into d.x and move the contents up, so that the tarball inside d is kept
    tmp = d + '.x'
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    subprocess.run(['tar', 'xf', tb, '-C', tmp, '--strip-components=1'], check=True)
    for f in os.listdir(tmp):
        shutil.move(os.path.join(tmp, f), os.path.join(d, f))
    os.rmdir(tmp)
    v = subprocess.run([f'{d}/bin/clang-14', '--version'],
                       capture_output=True, text=True).stdout.split('\n')[0]
    log('clang14 release:', v)


def step_wllvm():
    """pip --user install of the pinned wllvm."""
    w = WLLVM_BIN
    if os.path.exists(w):
        log('present', w)
        return
    run([sys.executable, '-m', 'pip', 'install', '--user', WLLVM_PIN])
    if not args.dry_run and not os.path.exists(w):
        die('wllvm install failed', w)


def step_kernels():
    """Download the 4 kernel tarballs (sha256 checked) into ~/rerun/src."""
    d = TARBALL_DIR
    for v, (vx, sha) in KERNELS.items():
        download(f'https://cdn.kernel.org/pub/linux/kernel/{vx}/linux-{v}.tar.xz',
                 f'{d}/linux-{v}.tar.xz', sha)
    # build_71_norand.sh (not included in the public artifact) looks at this path
    symlink(f'{d}/linux-7.1.4.tar.xz', f'{HOME}/linux-7.1.4.tar.xz')


def step_layout():
    """Restore the artifact's scripts and input data to their original locations on the
    measurement server and record rerun mode in env.local.sh."""
    if os.path.exists(LAYOUT_MARKER) and not args.force:
        die('the original layout of the measurement server already exists '
            '($HOME/rerun/nosan/build_14.log). Use --force to overwrite')
    W = args.work
    # (artifact folder, destination)
    M = [
        ('scripts/orig/nosan', f'{HOME}/rerun/nosan'),
        ('scripts/orig/fpea_pass', f'{HOME}/rerun/fpea_pass'),
        ('scripts/orig/final_scripts', f'{HOME}/fpea_gt/final/scripts'),
        ('scripts/orig/final', f'{HOME}/fpea_gt/final'),
        ('scripts/orig/epi_regfn', f'{HOME}/epi_regfn'),
        ('scripts/orig/scratchpad', W),
        ('tool/uafx', f'{HOME}/rerun/uafx_orig'),
        ('data/expert_pkg', f'{HOME}/fpea_gt/expert_pkg'),
        ('data/gt', f'{HOME}/rerun/fpea_pass'),
    ]
    for s, d in M:
        copy_tree(os.path.join(R, s), d)
    copy_tree(os.path.join(R, 'tool'), f'{HOME}/rerun/fpea_pass', only={'fpea.cpp', 'build.sh'})
    # inputs outside the reproduction scope: the UAFX whitelist (input), struct_drift based on
    # the KASAN 'full' tree (prior-work data)
    copy_tree(os.path.join(R, 'data/epi'), f'{HOME}/epi_regfn',
              only={'uafx_kernel_sts.json', 'struct_drift_full.json', 'struct_drift_full.log'})
    for t in ('fpea14', 'fpea16'):
        symlink(f'{R}/tool/{t}', f'{HOME}/rerun/fpea_pass/{t}')
    if not args.dry_run:
        for p in (f'{HOME}/rerun/uafx_orig/entry_point_handler_orig',
                  f'{R}/tool/uafx/entry_point_handler_orig'):
            if os.path.exists(p):
                os.chmod(p, 0o755)
        for d in (W, f'{W}/link', f'{HOME}/linux_bc', f'{HOME}/rerun/logs', f'{HOME}/rerun/results',
                  f'{HOME}/fpea_gt/final/figures', f'{HOME}/rerun/nosan/src_rb'):
            os.makedirs(d, exist_ok=True)
    # source trees for header parsing (handler_offset.py, intro_stats.py, filter_validate.py)
    # → the build trees.
    # filter_validate.py needs the debug (-g) tree when build_kernel.sh dbg has built it;
    # a later layout --force must not point the link back to the nosan tree
    dbg = f'{HOME}/rerun/dbg/src14/linux-5.17.11'
    symlink(dbg if os.path.isdir(dbg) else f'{HOME}/rerun/nosan/src14/linux-5.17.11',
            f'{HOME}/kernel/linux-5.17.11')
    symlink(f'{HOME}/rerun/nosan/src_rb/linux-5.19.17', f'{HOME}/kbuild/src/linux-5.19.17')
    symlink(f'{HOME}/rerun/nosan/src_rb/linux-6.9', f'{HOME}/kbuild/src/linux-6.9')
    symlink(f'{HOME}/rerun/nosan/src_rb/linux-7.1.4', f'{HOME}/linux-7.1.4')
    step_links()
    el = args.env_local
    log('write', el)
    if not args.dry_run:
        with open(el, 'w') as fh:
            fh.write(f'# File created by setup.py layout. This machine runs in rerun mode.\n'
                     f'export FPEA_MODE=rerun\nexport FPEA_WORK={W}\n')


def step_links():
    """Link the fixed paths of the original scripts (/tmp/*, the session scratchpad) to the
    work folder. Run again if /tmp is emptied after a reboot."""
    W = args.work
    T = args.tmp_root
    sc = scratch_link()
    if not args.dry_run:
        os.makedirs(os.path.dirname(sc), exist_ok=True)
        os.makedirs(f'{W}/link', exist_ok=True)
    symlink(W, sc)
    for name, tgt in (('units.txt', f'{W}/list_5.17.11.txt'),
                      ('u_fpea', f'{W}/rf_5.17.11'),
                      ('u_wl', f'{W}/rw_5.17.11'),
                      ('fpea_out', f'{W}/link/fpea_out'),
                      ('fpea14_out', f'{W}/link/fpea14_out'),
                      ('wl_out', f'{W}/link/wl_out'),
                      ('allfiles.txt', f'{W}/link/allfiles.txt')):
        symlink(tgt, f'{T}/{name}')


def step_verify_setup():
    """Check every toolchain, tarball, package and layout item; print an OK/MISSING line each."""
    ok = True

    def chk(name, cond, detail=''):
        nonlocal ok
        ok &= bool(cond)
        print(f'  [{"OK" if cond else "MISSING"}] {name} {detail}')

    def ver(p):
        try:
            return subprocess.run([p, '--version'], capture_output=True,
                                  text=True).stdout.split('\n')[0]
        except Exception:
            return ''

    v = ver(LLVM14_SYS_CLANG)
    chk('clang 14 (Ubuntu package)', '14.0.0' in v, v)
    chk('llvm-dis-14 / llvm-link-14',
        os.path.exists('/usr/bin/llvm-dis-14') and os.path.exists('/usr/bin/llvm-link-14'))
    chk('llvm-config-14 (fpea14 build)', shutil.which('llvm-config-14'))
    v = ver(f'{LLVM16_LINK}/bin/clang')
    chk('clang 16.0.6 (~/llvm/build → apt.llvm.org)', '16.0.6' in v, v)
    chk('  same commit 7cbf1a259152', LLVM16_COMMIT[:12] in v)
    chk('  llvm-config/llvm-dis/llvm-link 16',
        all(os.path.exists(f'{LLVM16_LINK}/bin/{t}')
            for t in ('llvm-config', 'llvm-dis', 'llvm-link')))
    v = ver(f'{LLVM14_DIR}/bin/clang-14')
    chk('clang 14.0.6 release (~/llvm-14.0.7)', '14.0.6' in v, v)
    chk('wllvm', os.path.exists(WLLVM_BIN))
    for k, (vx, sha) in KERNELS.items():
        p = f'{TARBALL_DIR}/linux-{k}.tar.xz'
        chk(f'tarball {k}', os.path.exists(p) and sha256(p) == sha, p)
    for m in ('matplotlib', 'numpy'):
        importable = subprocess.run([sys.executable, '-c', f'import {m}'], capture_output=True)
        chk(f'python3 {m}', importable.returncode == 0)
    for t in ('make', 'flex', 'bison', 'bc'):
        chk(t, shutil.which(t))
    pahole = 'OK' if shutil.which('pahole') else 'NOTE'
    print(f'  [{pahole}] pahole (dwarves; not needed since only drivers/ is built)')
    chk('layout: ~/rerun/fpea_pass/hitrate_full.py',
        os.path.exists(f'{HOME}/rerun/fpea_pass/hitrate_full.py'))
    chk('layout: ~/fpea_gt/expert_pkg/rA.csv', os.path.exists(f'{HOME}/fpea_gt/expert_pkg/rA.csv'))
    chk('layout: env.local.sh (rerun mode)', os.path.exists(args.env_local))
    sc = scratch_link()
    chk('links: scratchpad → work folder', os.path.islink(sc))
    free_gb = shutil.disk_usage(HOME).free / 2**30
    chk('free disk ≥ 70 GB', free_gb >= MIN_DISK_GB, f'{free_gb:.1f} GB')
    print('setup', 'OK' if ok else 'incomplete — check the items above')
    return ok


STEPS = {
    'check': step_check,
    'apt': step_apt,
    'llvm16': step_llvm16,
    'llvm14': step_llvm14,
    'wllvm': step_wllvm,
    'kernels': step_kernels,
    'layout': step_layout,
    'links': step_links,
    'verify-setup': step_verify_setup,
}
ORDER = ['check', 'apt', 'llvm16', 'llvm14', 'wllvm', 'kernels', 'layout', 'verify-setup']


# ---------------------------------------------------------------- main
def parse_args():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('steps', nargs='*', default=['check'],
                    help='check apt llvm16 llvm14 wllvm kernels layout links verify-setup all')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--work', default=f'{HOME}/fpea_work')
    ap.add_argument('--tmp-root', default='/tmp')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--no-sudo', action='store_true', default=False)
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--env-local', default=os.path.join(R, 'env.local.sh'),
                    help='file where layout records rerun mode (default repro/env.local.sh)')
    opts = ap.parse_args()
    opts.work = os.path.abspath(os.path.expanduser(opts.work))
    return opts


def main():
    global args
    args = parse_args()
    steps = ORDER if args.steps == ['all'] else args.steps
    for s in steps:
        if s not in STEPS:
            die('unknown step', s)
        log(f'=== {s} ===' if not args.quiet else '')
        t0 = time.time()
        STEPS[s]()
        log(f'=== {s} done ({time.time() - t0:.0f}s)')


if __name__ == '__main__':
    main()

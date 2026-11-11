"""Shared constants of the v2.3 audit scripts (2026-11-09, second-author peer review).

The scripts in this folder were written during the audit of the negative-sample design, the
AT-only tagging and the whitelist-only decomposition. They read the same environment variables as
env.sh; the defaults are the measurement server's paths (the original versions used /tmp/units.txt
and /tmp/u_fpea written by the 2026-11-09 session).
"""
import os
import re

E = os.environ.get
HOME = E('FPEA_HOME') or os.path.expanduser('~')   # root of the original layout (env.sh)
REPRO = E('FPEA_REPRO', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
OUTD = E('FPEA_OUT', f'{REPRO}/data/fpea_out')
UNITS = E('FPEA_UNITS', f'{OUTD}/list_5.17.11.txt')          # 5.17.11 clang14 unit list
RF = E('FPEA_RF_517', f'{OUTD}/rf_5.17.11')                   # fpea16 --unit output (typed bitcode)
RF14 = E('FPEA_RF14_517', f'{OUTD}/rf14_5.17.11')             # fpea14 --unit output (same bitcode)
RW = E('FPEA_RW_517', f'{OUTD}/rw_5.17.11')                   # UAFX unit output
LINKOUT = E('FPEA_LINKOUT', f'{REPRO}/data/link/fpea_out')    # link-layer fpea16 output
ALLF = E('FPEA_ALLFILES', os.path.join(os.path.dirname(LINKOUT.rstrip('/')), 'allfiles.txt'))
RESULTS = E('FPEA_RESULTS', f'{REPRO}/data/results')          # stored results
OUTDIR = E('FPEA_AUDIT_OUT', E('FPEA_OUTDIR', f'{REPRO}/out'))  # where the scripts write
DIS14 = E('FPEA_DIS14', '/usr/bin/llvm-dis-14')
DIS16 = E('FPEA_DIS16', f'{HOME}/llvm/build/bin/llvm-dis')
GT = E('FPEA_GT_SAMPLE', f'{REPRO}/data/gt/gt_sample_unit.json')
# unit list of the original draw (measurement-server find order) and the 500 stage-1 units it
# selects with seed 913, as relative paths; see selected_units()
UNITS_ORIG = E('FPEA_UNITS_ORIG', f'{REPRO}/data/fpea_out/list_5.17.11.txt')
STAGE1 = E('FPEA_STAGE1_UNITS', f'{REPRO}/data/gt/stage1_units_500.txt')
SRC_MARK = '/linux-5.17.11/'   # the unit paths are recorded relative to the source tree
NPROC = int(E('FPEA_NPROC', '14'))

# Section 3.4 compiler-symbol filter, as used by fpea.cpp (ContamUnit) and sample_gt_unit.py
CONTAM = re.compile(r'(\.\d+$|\.(constprop|isra|part|cold)\b|^asan\.|^__asan|^kasan\.|^__ubsan'
                    r'|^ubsan\.|^__bpf_trace_|^trace_event_raw_event_|^perf_trace_'
                    r'|^trace_raw_output_|^__traceiter_|^__probestub_|^rcu_lock_|^local_bh_'
                    r'|^__local_bh_|^llvm\.|^__cfi_|^__pfx_|^__x86_indirect|^__sanitizer_cov)')
DEFINE_RE = re.compile(r'^define[^@]*@([\w.$]+)\(', re.M)


def units():
    return [l.strip() for l in open(UNITS) if l.strip()]


def relunit(p):
    """/…/src14/linux-5.17.11/drivers/x/.y.o.bc -> drivers/x/.y.o.bc (result files hold this form so
    that a re-run under another root compares equal)."""
    return p.split(SRC_MARK, 1)[1] if SRC_MARK in p else p


def unit_root(lst=None):
    """Root of the current unit list up to and including linux-5.17.11/ ('' if the list is
    already relative)."""
    u = (lst or units())[0]
    return u[:u.index(SRC_MARK) + len(SRC_MARK)] if SRC_MARK in u else ''


def rf_json(f, d=None):
    """Per-unit fpea json path of unit f (path with / replaced by _)."""
    return f'{d or RF}/{f.replace("/", "_")}.json'


def module_name(f):
    """drivers/x/.name.o.bc -> name (the 'module' column of the reference set)."""
    return os.path.basename(f)[1:].replace('.o.bc', '')


def selected_units(seed=913, n=500):
    """The stage-1 negative sample of sample_gt_unit.py: the 500 units that the seed-913 shuffle of
    the original unit list selects, in that order (boot2 draws from it in this order).

    The shuffle is order-sensitive and the unit list is written in filesystem order, so a
    regenerated list selects other units (13 of 500 coincide on the 2026-11-11 reproduction VM).
    The selection is therefore fixed: data/gt/stage1_units_500.txt (relative paths, derived once
    from the stored list), joined with the root of the current unit list. Without that file the
    stored original list is shuffled; the current list only as a last resort."""
    import random
    root = unit_root()
    if os.path.exists(STAGE1):
        return [root + l.strip() for l in open(STAGE1) if l.strip()]
    um = [relunit(l.strip()) for l in open(UNITS_ORIG if os.path.exists(UNITS_ORIG) else UNITS)
          if l.strip()]
    random.seed(seed)
    random.shuffle(um)
    return [root + u for u in um[:n]]


def outpath(name):
    os.makedirs(OUTDIR, exist_ok=True)
    return os.path.join(OUTDIR, name)

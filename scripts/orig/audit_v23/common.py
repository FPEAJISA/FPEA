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
NPROC = int(E('FPEA_NPROC', '14'))

# Section 3.4 compiler-symbol filter, as used by fpea.cpp (ContamUnit) and sample_gt_unit.py
CONTAM = re.compile(r'(\.\d+$|\.(constprop|isra|part|cold)\b|^asan\.|^__asan|^kasan\.|^__ubsan'
                    r'|^ubsan\.|^__bpf_trace_|^trace_event_raw_event_|^perf_trace_'
                    r'|^trace_raw_output_|^__traceiter_|^__probestub_|^rcu_lock_|^local_bh_'
                    r'|^__local_bh_|^llvm\.|^__cfi_|^__pfx_|^__x86_indirect|^__sanitizer_cov)')
DEFINE_RE = re.compile(r'^define[^@]*@([\w.$]+)\(', re.M)


def units():
    return [l.strip() for l in open(UNITS) if l.strip()]


def rf_json(f, d=None):
    """Per-unit fpea json path of unit f (path with / replaced by _)."""
    return f'{d or RF}/{f.replace("/", "_")}.json'


def module_name(f):
    """drivers/x/.name.o.bc -> name (the 'module' column of the reference set)."""
    return os.path.basename(f)[1:].replace('.o.bc', '')


def selected_units(seed=913, n=500):
    """The stage-1 negative sample: shuffle the unit list with seed 913, take the first 500
    (sample_gt_unit.py)."""
    import random
    um = units()[:]
    random.seed(seed)
    random.shuffle(um)
    return um[:n]


def outpath(name):
    os.makedirs(OUTDIR, exist_ok=True)
    return os.path.join(OUTDIR, name)

"""Link-layer aggregation of FPEA entry points (analyze3).

Reads /tmp/allfiles.txt (linked .bc units), /tmp/fpea_out/<unit>.json (FPEA output),
/tmp/wl_out/<unit>.txt (UAFX baseline) and, through llvm-dis, the IR of every unit.
Prints report sections 1-2 to stdout (stored as data/results/analyze3.log) and writes
analyze3.json (read by derive/verify).  Invoked as `python3 analyze3.py > analyze3.log`.
"""
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from multiprocessing import Pool

ALLFILES = '/tmp/allfiles.txt'
FPEA_OUT_DIR = '/tmp/fpea_out/'
WL_OUT_DIR = '/tmp/wl_out/'
OUT_JSON = 'analyze3.json'
DIS = os.path.expanduser('~/llvm/build/bin/llvm-dis')
DIS_TIMEOUT = 900
POOL_SIZE = 14
CHUNKSIZE = 6
SIGNALS = ('C1', 'C2', 'C3', 'C4', 'C5')

# Regexes over the textual IR (patterns are verbatim; do not reflow).
BA = re.compile(r'blockaddress\(@[\w.$]+,\s*%[\w.$]+\)')
SYM = re.compile(r'(?<![\w.])@([\w.$]+)(?![\w.(])')
CONTAM = re.compile(r'(\.(constprop|isra|part|cold)(\.\d+)?$|^asan\.|^__asan|^kasan\.|^__ubsan|^ubsan\.|^__bpf_trace_|^trace_event_raw_event_|^perf_trace_|^trace_raw_output_|^__traceiter_|^__probestub_|^rcu_lock_|^local_bh_|^__local_bh_|^llvm\.|^__cfi_|^__pfx_|^__x86_indirect|^__sanitizer_cov)')
ITER = re.compile(r'^(sort|sort_r|list_sort|bsearch|bus_for_each_\w+|driver_for_each_device|device_for_each_child\w*|class_for_each_device|idr_for_each|klist_\w+|\w+_for_each\w*|\w+_walk\w*|\w+_iterate\w*|iterate_\w+|walk_\w+|device_find_child|class_find_device|bus_find_device|__hw_addr_sync\w*|on_each_cpu\w*|alloc_netdev_mqs|usb_add_config|__dma_request_channel|devres_release|comedi_timeout|v4l2_m2m_ctx_init)$')
PRINTK = re.compile(r'^(_printk|printk|.*_dbg_trace|.*_debug|dev_\w+|netdev_\w+|seq_printf|snprintf|sprintf|scnprintf|panic)$')
DEFINE_RE = re.compile(r'^define[^@]*@([\w.$]+)\(', re.M)
DECLARE_RE = re.compile(r'^declare[^@]*@([\w.$]+)\(', re.M)
CALL_RE = re.compile(r'\bcall\b[^\n]*?@([\w.$]+)\(([^\n]*)\)')


def fpea_json_path(bc):
    """FPEA output JSON for a unit path."""
    return FPEA_OUT_DIR + bc.replace('/', '_') + '.json'


def wl_path(bc):
    """UAFX baseline (whitelist) text file for a unit path."""
    return WL_OUT_DIR + bc.replace('/', '_') + '.txt'


def read_baseline(bc):
    """Map function -> first baseline kind seen, from the `kind:function` lines."""
    baseline = {}
    if os.path.exists(wl_path(bc)):
        for line in open(wl_path(bc), errors='replace'):
            parts = line.strip().split(':')
            if len(parts) >= 2:
                baseline.setdefault(parts[1], parts[0])
    return baseline


def disassemble(bc):
    """Textual IR of a unit with blockaddress operands neutralised."""
    proc = subprocess.run([DIS, '-o', '-', bc], capture_output=True, text=True,
                          timeout=DIS_TIMEOUT)
    return BA.sub('blockaddress(BA)', proc.stdout)


def address_taken(ll, clean):
    """Clean defined functions whose symbol appears anywhere outside metadata/comments."""
    taken = set()
    for line in ll.split('\n'):
        if line.startswith('!') or line.startswith(';'):
            continue
        for sym in SYM.findall(line):
            if sym in clean:
                taken.add(sym)
    return taken


def c3_only_sync_fps(ll, entries):
    """C3-only entry points passed as arguments to iterator/printk-style synchronous APIs."""
    fp_sync = set()
    for line in ll.split('\n'):
        call = CALL_RE.search(line)
        if not call:
            continue
        callee = call.group(1)
        if ITER.match(callee) or PRINTK.match(callee):
            for sym in SYM.findall(call.group(2)):
                if sym in entries and set(entries[sym]) == {'C3'}:
                    fp_sync.add(sym)
    return fp_sync


def analyze_unit(bc):
    """Pool worker: (entries, defined, baseline, address-taken, declared, clean, C3 sync FPs)."""
    try:
        fpea = json.load(open(fpea_json_path(bc)))
    except Exception:
        return None
    entries = fpea['entries']
    entry_set = set(entries)
    defined_count = fpea['defined']
    baseline = read_baseline(bc)
    # address-taken + FP causes: parse the IR once
    ll = disassemble(bc)
    clean = {x for x in DEFINE_RE.findall(ll) if not CONTAM.search(x)}
    declared = {x for x in DECLARE_RE.findall(ll)}
    taken = address_taken(ll, clean)
    # FP causes for C3-only entry points (synchronous-call APIs)
    fp_sync = c3_only_sync_fps(ll, entries)
    return entry_set, defined_count, baseline, taken, declared, clean, fp_sync


def signal_distribution(files):
    """Signal histogram and C4-only count straight from the FPEA JSON files (sequential)."""
    sig = Counter()
    c4_only = 0
    n_entries = 0
    for bc in files:
        try:
            entries = json.load(open(fpea_json_path(bc)))['entries']
        except Exception:
            continue
        for fn, signals in entries.items():
            n_entries += 1
            signal_set = set(signals)
            for x in signal_set:
                sig[x] += 1
            if signal_set == {'C4'}:
                c4_only += 1
    return sig, c4_only, n_entries


def main():
    files = [line.strip() for line in open(ALLFILES)]
    fpea_total = 0
    defined_total = 0
    wl_kind = Counter()
    inter = 0
    wl_minus_fpea = 0
    wl_miss = Counter()
    at_total = 0
    only_fpea = only_at = both = 0
    fp_sync_total = set()
    with Pool(POOL_SIZE) as pool:
        for result in pool.imap_unordered(analyze_unit, files, chunksize=CHUNKSIZE):
            if not result:
                continue
            entry_set, defined_count, baseline, taken, declared, clean, fp_sync = result
            fpea_total += len(entry_set)
            defined_total += defined_count
            at_total += len(taken)
            only_fpea += len(entry_set - taken)
            only_at += len(taken - entry_set)
            both += len(entry_set & taken)
            fp_sync_total |= fp_sync
            # relation to baseline
            for fn, kind in baseline.items():
                wl_kind[kind] += 1
                if fn in entry_set:
                    inter += 1
                else:
                    wl_minus_fpea += 1
                    if fn in clean:
                        cat = 'defined'
                    elif fn in declared:
                        cat = 'external'
                    else:
                        cat = 'other'
                    wl_miss[(kind, cat)] += 1

    # signal distribution / conservative lower bound directly from fpea_out
    sig, c4_only, n_entries = signal_distribution(files)

    print("=== 1. Relation to baseline (link layer, original UAFX, sanitizer off) ===")
    print(f"  FPEA {fpea_total}  defined functions {defined_total}"
          f"  entry-point ratio {fpea_total/defined_total*100:.1f}%")
    print(f"  baseline {sum(wl_kind.values())} ({dict(wl_kind)})")
    print(f"  ∩ {inter}   WL\\FPEA {wl_minus_fpea}"
          f"   miss rate {(fpea_total-inter)/fpea_total*100:.2f}%")
    top_miss = sorted(wl_miss.items(), key=lambda x: -x[1])[:6]
    print("  WL\\FPEA breakdown:", {f"{k}|{cat}": n for (k, cat), n in top_miss})
    print(f"\n=== 2. Versus address-taken + conservative lower bound ===")
    print(f"  address-taken {at_total} ({at_total/defined_total*100:.1f}%)"
          f"   FPEA {fpea_total} ({fpea_total/defined_total*100:.1f}%)")
    print(f"  both {both}  FPEA only {only_fpea}  AT only {only_at}")
    print(f"  signal distribution: "
          + "  ".join(f"{k} {sig[k]}({sig[k]/n_entries*100:.1f}%)" for k in SIGNALS))
    lower_bound = fpea_total - c4_only
    print(f"  C4 only (excluded in the conservative count) {c4_only}"
          f" → conservative lower bound {lower_bound} ({lower_bound/defined_total*100:.1f}%)")
    print(f"  C3-only FPs via synchronous-call APIs {len(fp_sync_total)}")

    summary = dict(FPEA=fpea_total, defined=defined_total, baseline=sum(wl_kind.values()),
                   I=inter, WmF=wl_minus_fpea, miss=(fpea_total-inter)/fpea_total,
                   wl_kind=dict(wl_kind),
                   wl_miss={f"{k}|{c}": n for (k, c), n in wl_miss.items()},
                   AT=at_total, onlyF=only_fpea, onlyAT=only_at, both=both, sig=dict(sig),
                   c4solo=c4_only, c3sync=len(fp_sync_total))
    with open(OUT_JSON, 'w') as out:
        json.dump(summary, out, indent=1)


if __name__ == '__main__':
    main()

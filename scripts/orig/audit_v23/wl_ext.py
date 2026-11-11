#!/usr/bin/env python3
"""Whitelist-only pairs of Section 5.3 / Supplementary Table S3, step 2 (light).

From wl_only.json (step 1), the symbol map defmap_5.17.11.tsv.gz (llvm-nm) and the link-layer
FPEA output:
  698 declared pairs -> unique names; defined in drivers/ (defmap) or outside; of those in
  drivers/, identified by FPEA in the defining unit, or not; of the latter, static-call
  trampolines (__SCT__tp_func_*, tracepoint by-products reported by signature) vs real handlers;
  real handlers recovered at the link layer or not (inter-module registration / direct call only).
  289 defined pairs -> tracepoint by-products (25) vs real ioctl handlers (264); link recovered.
  The two rows overlap (a handler defined in its unit is also declared in client units):
  shared handlers by name = |ext_other_unit_registered ∪ defined_real| (372; rows 342 + 264 = 606
  count 234 names twice), link recovered 304 (rows 304 + 224 = 528), remaining 68 (rows 38 + 40 = 78).
Output wl_ext.json."""
import collections
import gzip
import json
import os
import re

from common import LINKOUT, OUTDIR, RESULTS, outpath

TR = re.compile(r'^(__bpf_trace_|perf_trace_|trace_event_raw_event_|trace_raw_output_'
                r'|__traceiter_|__probestub_)')
SCT = re.compile(r'^__SCT__')


def pick(name):
    p = f'{OUTDIR}/{name}'
    return p if os.path.exists(p) else f'{RESULTS}/{name}'


def main():
    w = json.load(open(pick('wl_only.json')))
    defmap = collections.defaultdict(set)
    with gzip.open(os.environ.get('FPEA_DEFMAP', pick('defmap_5.17.11.tsv.gz')), 'rt') as fh:
        for l in fh:
            fn, u = l.rstrip('\n').split('\t')
            defmap[fn].add(u)
    link = set()
    for jf in os.listdir(LINKOUT):
        link |= set(json.load(open(f'{LINKOUT}/{jf}'))['entries'])
    fpea_names = set()
    # FPEA entry names over all units: the rows carry only WL-only pairs, so read rf directly
    from common import RF, rf_json, units
    for u in units():
        p = rf_json(u, RF)
        if os.path.exists(p):
            fpea_names |= set(json.load(open(p))['entries'])
    ext = {fn for u, fn, k, c in w['rows'] if c == 'declared'}
    dfn = {fn for u, fn, k, c in w['rows'] if c == 'defined'}
    in_drv = {fn for fn in ext if fn in defmap}
    outside = sorted(ext - in_drv)
    hit = {fn for fn in in_drv if fn in fpea_names}
    miss = in_drv - hit
    sct = {fn for fn in miss if SCT.match(fn)}
    real_ext = miss - sct
    tr = {fn for fn in dfn if TR.match(fn)}
    real_def = dfn - tr
    out = dict(
        ext_pairs=w['ext_pairs'], ext_unique=len(ext), ext_in_drivers=len(in_drv),
        ext_outside_drivers=outside, ext_fpea_hit_own_unit=sorted(hit),
        ext_fpea_miss=len(miss), ext_static_call_trampolines=sorted(sct),
        ext_other_unit_registered=len(real_ext),
        ext_link_recovered=len(real_ext & link), ext_link_unrecovered=sorted(real_ext - link),
        defined_pairs=w['defined_not_fpea'], defined_unique=len(dfn),
        defined_trace_artifacts=sorted(tr), defined_real=len(real_def),
        defined_link_recovered=len(real_def & link),
        defined_link_unrecovered=sorted(real_def - link),
        shared_handlers_total=len(real_ext) + len(real_def),
        shared_link_recovered=len(real_ext & link) + len(real_def & link),
        shared_link_unrecovered=len(real_ext - link) + len(real_def - link),
        # The two rows count the same function twice when a handler defined in its unit is
        # also reported as an external symbol in client units: merge by name.
        row_overlap_names=sorted(real_ext & real_def),
        shared_unique_total=len(real_ext | real_def),
        shared_unique_link_recovered=len((real_ext | real_def) & link),
        shared_unique_link_unrecovered=len((real_ext | real_def) - link),
        wl_only_unique_functions=len(ext | dfn))
    print(json.dumps({k: (v if not isinstance(v, list) else len(v)) for k, v in out.items()},
                     indent=1))
    json.dump(out, open(outpath('wl_ext.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()

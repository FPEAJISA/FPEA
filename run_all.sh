#!/usr/bin/env bash
# Full reproduction driver for the FPEA paper.
#   ./run_all.sh                  = derive + verify   (artifact mode: stored outputs under data/, no bitcode needed, a few minutes)
#   ./run_all.sh verify-heavy     = also the IR re-interpretation checks (needs the bitcode trees)
# The stages below run only in rerun mode (recorded in env.local.sh by setup.py layout). On a new machine: setup.py all → ./run_all.sh all.
#   build-kernels  0 : build 6 kernels + collect unit bitcode + link layer + 1 debug build (for the 3.4 filter validation) (hours, ~50 GB)
#   build-tools    1 : build fpea14 / fpea16
#   run-fpea       2 : FPEA + UAFX on 5 trees, performance measurement, opaque units, link layer (FPEA, UAFX, fpea14)
#   analyses       3 : hit rate, semantic hit rate, named/literal, placeholder, kind_drift, UAF subset, link-layer decomposition, behaviour classification, header offset, placeholder experiment
#   sample         4a: reference-set sampling (for reference only; the original sample is preserved)
#   pilots         5 : top-caller pilot
#   figures        6 : figures
#   derive         D : regenerate derived results + compare with stored copies; in rerun also the metric scripts (final_calc_expert, review_check)
#   verify[-heavy] V : compare paper numbers
#   all              : 0 → V
#
# Layout of this file: environment + helpers, one function per stage (in stage order), and the
# stage dispatcher at the bottom. Every `say` line is appended to logs/run_all.log; the message
# texts are kept fixed so that logs of different runs can be compared.
set -u
cd "$(dirname "$0")"
source ./env.sh

# --- shared paths (the FPEA_* variables come from env.sh) ---
R=$FPEA_REPRO
S=$R/scripts
OR=$S/orig
L=$R/logs
mkdir -p $L $FPEA_OUTDIR

# say <message>: time-stamped progress line on stdout, also appended to logs/run_all.log
say(){
  echo "[$(date '+%m/%d %H:%M:%S')] $*" | tee -a $L/run_all.log
}

stage=${1:-derive}

# need_rerun: abort (exit 2) unless env.sh / env.local.sh selected rerun mode
need_rerun(){
  [ "$FPEA_MODE" = rerun ] || {
    say "stage '$stage' runs only in rerun mode (protects the stored outputs under data/ in artifact mode). Run setup.py layout first."
    exit 2
  }
}

# original layout folders of rerun mode (created by setup.py layout)
if [ "$FPEA_MODE" = rerun ]; then
  NOSAND=$FPEA_NOSAN_DIR   # $HOME/rerun/nosan
  PASSD=$FPEA_PASS_DIR     # $HOME/rerun/fpea_pass
  EPID=$FPEA_EPI_DIR       # $HOME/epi_regfn
  FIN=$FPEA_FIN            # $HOME/fpea_gt/final
  FINS=$FIN/scripts
  SPD=$FPEA_WORK           # stands in for the original session scratchpad
  mkdir -p $FPEA_WORK/link $FIN/scripts $FIN/figures
fi

# links: link the fixed /tmp paths and the session scratchpad read by the original scripts to the
# work folder (after a reboot, run setup.py layout again if needed)
links(){
  python3 $S/setup.py links --work "$FPEA_WORK" --quiet || true
}

# --- stage 0: kernel builds (6 trees + debug build) and the llvm-link layer ---
build_kernels(){
  need_rerun
  say "0) kernel builds (wllvm, allmodconfig, sanitizer off, drivers/ only) — clang14: 5.17.11·5.19.17·6.9, clang16: 5.17.11·7.1.4·7.1.4-norand"
  bash $S/build_kernel.sh 5.17.11 14 || exit 1
  bash $S/build_kernel.sh 5.17.11 16 || exit 1
  bash $S/build_kernel.sh 5.19.17 14 || exit 1
  bash $S/build_kernel.sh 6.9 14 || exit 1
  bash $S/build_kernel.sh 7.1.4 16 || exit 1
  bash $S/build_kernel.sh 7.1.4 16 norand || exit 1
  say "   debug build (5.17.11 clang14, allmodconfig as is + KCFLAGS=-g; for the 3.4 contamination-filter validation, recipe of the measurement server's $HOME/kernel/linux-5.17.11)"
  bash $S/build_kernel.sh 5.17.11 14 dbg || exit 1
  say "   link layer (llvm-link of the 5.17.11 clang14 units per .mod) → $FPEA_LINKBC"
  bash $OR/nosan/build_linked.sh 14
}

# --- stage 1: build the FPEA binaries ---
build_tools(){
  say "1) build fpea14 / fpea16 (tool/fpea.cpp)"
  (cd $R/tool && bash build.sh) || exit 1
}

# --- stage 2: FPEA + UAFX on the 5 unit trees, wall-clock measurement, opaque units, link layer ---
# Per tree: list_<V>.txt (units), rf_<V>/ (FPEA json per unit), rw_<V>/ (UAFX txt per unit) under
# $FPEA_OUT; timings in $FIN/version_measure.log and $FIN/fpea_timing.txt; link layer under
# $FPEA_WORK/link. The xargs templates are single-quoted sh code with the tool/output paths spliced
# in; every unit's failure is ignored (exit 0) so that xargs keeps going.
run_fpea(){
  need_rerun
  links
  say "2) FPEA unit runs + original UAFX runs (5 trees) → $FPEA_OUT"
  FPEA=$R/tool/fpea16
  UAFX=$FPEA_UAFX_TOOL
  VM=$FIN/version_measure.log
  : > $VM
  declare -A TREE=(
    [5.17.11]=$FPEA_SRC14
    [5.19.17]=$FPEA_BC_519
    [6.9]=$FPEA_BC_69
    [7.1.4]=$FPEA_BC_714
    [7.1.4-norand]=$FPEA_BC_714N
  )
  for V in 5.17.11 5.19.17 6.9 7.1.4 7.1.4-norand; do
    T=${TREE[$V]}
    OF=$FPEA_OUT/rf_$V
    OW=$FPEA_OUT/rw_$V
    rm -rf $OF $OW
    mkdir -p $OF $OW
    LST=$FPEA_OUT/list_$V.txt
    # 5.17.11 units = the .name.o.bc under drivers/ + scripts/mod/empty +
    # tools/testing/nvdimm/test/iomap (excluding the modpost by-product .mod.o.bc) = 15,522
    if [ "$V" = 5.17.11 ]; then
      find $T/drivers $T/scripts $T/tools -name '.*.o.bc' ! -name '*.mod.o.bc' | sort > $LST
    else
      find $T -path '*/drivers/*' -name '*.o.bc' | sort > $LST
    fi
    echo "[$V] bitcode $(wc -l < $LST)" >> $VM
    say "   $V units $(wc -l < $LST)"
    # FPEA (fpea16, --unit) on every unit of the list
    S0=$(date +%s)
    xargs -P $FPEA_NPROC -I{} \
      sh -c 'f="{}"; n=$(echo "$f"|tr / _); '"$FPEA"' "$f" "'$OF'/$n.json" --unit >/dev/null 2>&1; exit 0' < $LST
    echo "[$V] FPEA done $(( $(date +%s)-S0 ))s, json $(ls $OF | wc -l)" >> $VM
    say "   $V FPEA $(( $(date +%s)-S0 ))s"
    case $V in
      7.1.4*)
        echo "[$V] UAFX skipped (clang16 bitcode, LLVM14 tool reads 0)" >> $VM
        continue;;
    esac
    # original UAFX tool (LLVM14) on the same units, 300 s limit per unit
    S0=$(date +%s)
    xargs -P $FPEA_NPROC -I{} \
      sh -c 'f="{}"; n=$(echo "$f"|tr / _); timeout 300 '"$UAFX"' "$f" "'$OW'/$n.txt" >/dev/null 2>&1; exit 0' < $LST
    echo "[$V] UAFX done $(( $(date +%s)-S0 ))s, txt $(ls $OW | wc -l)" >> $VM
    say "   $V UAFX $(( $(date +%s)-S0 ))s"
  done
  echo ALLDONE >> $VM

  say "   performance: 5.17.11 sequential / 14-parallel wall-clock → $FIN/fpea_timing.txt"
  OUTT=$FPEA_WORK/timing_tmp
  rm -rf $OUTT
  mkdir -p $OUTT
  # sequential pass: one unit after the other
  S0=$(date +%s.%N)
  while IFS= read -r f; do
    n=$(echo "$f"|tr / _)
    "$FPEA" "$f" "$OUTT/$n.json" --unit >/dev/null 2>&1
  done < $FPEA_OUT/list_5.17.11.txt
  E0=$(date +%s.%N)
  echo "sequential_wall_sec $(echo "$E0-$S0"|bc)" > $FIN/fpea_timing.txt
  # parallel pass: 14 workers
  S0=$(date +%s.%N)
  xargs -P 14 -I{} \
    sh -c 'f="{}"; n=$(echo "$f"|tr / _); '"$FPEA"' "$f" '"$OUTT"'/p_$n.json --unit >/dev/null 2>&1' < $FPEA_OUT/list_5.17.11.txt
  E0=$(date +%s.%N)
  echo "parallel14_wall_sec $(echo "$E0-$S0"|bc)" >> $FIN/fpea_timing.txt
  echo DONE >> $FIN/fpea_timing.txt
  rm -rf $OUTT

  say "   opaque units (5.17.11 clang16) → rf_nosan16"
  find $FPEA_BC16 -path '*/drivers/*' -name '*.o.bc' | sort > $FPEA_OUT/list_nosan16.txt
  OF=$FPEA_OUT/rf_nosan16
  rm -rf $OF
  mkdir -p $OF
  xargs -P $FPEA_NPROC -I{} \
    sh -c 'f="{}"; n=$(echo "$f"|tr / _); '"$FPEA"' "$f" "'$OF'/$n.json" --unit >/dev/null 2>&1; exit 0' < $FPEA_OUT/list_nosan16.txt

  say "   link layer: list of files to analyse (modules + builtin + replacement units of modules that failed to link) → link/allfiles.txt"
  LK=$FPEA_WORK/link
  mkdir -p $LK
  # allfiles.txt = linked modules + builtin objects + the single units of every module whose
  # llvm-link failed (listed as "FAIL <mod>" in link_report.txt; the first line of the .mod file
  # names the module's object files). O = linked bitcode dir, S = 5.17.11 clang14 source tree.
  python3 - "$FPEA_LINKBC" "$FPEA_SRC14" "$LK/allfiles.txt" <<'PY'
import glob
import os
import sys

O, S, out = sys.argv[1:4]
files = sorted(glob.glob(f'{O}/modules/*.bc')) + sorted(glob.glob(f'{O}/builtin/*.bc'))
for line in open(f'{O}/link_report.txt'):
    if line.startswith('FAIL'):
        mod = line.split()[1]
        for o in open(f'{S}/{mod}').read().split('\n')[0].split():
            unit = f'{S}/{os.path.dirname(o)}/.{os.path.basename(o)}.bc'
            if os.path.exists(unit):
                files.append(unit)
files = list(dict.fromkeys(files))   # drop units shared by several failed modules
with open(out, 'w') as fh:
    fh.write('\n'.join(files) + '\n')
print('allfiles', len(files))
PY
  say "   link layer fpea16 / UAFX / fpea14 → $LK/{fpea_out,wl_out,fpea14_out}"
  rm -rf $LK/fpea_out $LK/wl_out $LK/fpea14_out
  mkdir -p $LK/fpea_out $LK/wl_out $LK/fpea14_out
  # fpea16 (whole-module mode, no --unit) on every linked file
  xargs -P $FPEA_NPROC -I{} \
    sh -c 'f="{}"; n=$(echo "$f"|tr / _); '"$FPEA"' "$f" "'$LK'/fpea_out/$n.json" >/dev/null 2>&1; exit 0' < $LK/allfiles.txt
  # UAFX on every linked file
  xargs -P $FPEA_NPROC -I{} \
    sh -c 'f="{}"; n=$(echo "$f"|tr / _); timeout 300 '"$UAFX"' "$f" "'$LK'/wl_out/$n.txt" >/dev/null 2>&1; exit 0' < $LK/allfiles.txt
  # fpea14 (typed IR) on the linked files only — the src14 replacement units are skipped
  grep -v "src14" $LK/allfiles.txt \
    | xargs -P $FPEA_NPROC -I{} sh -c 'f="{}"; n=$(echo "$f"|tr / _); '$R'/tool/fpea14 "$f" "'$LK'/fpea14_out/$n.json" >/dev/null 2>&1; exit 0'
  say "   link-layer outputs: fpea16 $(ls $LK/fpea_out | wc -l), UAFX $(ls $LK/wl_out | wc -l), fpea14 $(ls $LK/fpea14_out | wc -l)"
}

# lit16_scan <list> <out>: count named / strict-literal patterns of file_operations globals in
# opaque IR (llvm-dis 16). This is the lit16 block of measure_714_norand.sh (not included in the
# public artifact). The template is sh code: llvm-dis to stdout, grep the fops globals, map each to
# its struct name or LITERAL_FOPS, count, prefix with the unit path.
lit16_scan(){
  : > "$2"
  xargs -P $FPEA_NPROC -I{} \
    sh -c "$FPEA_DIS16"' -o - "{}" 2>/dev/null | grep -E "^@[^ ]+ = [^{]*(constant|global) (%struct\.file_operations \{|\{ (ptr, ){25,}[^}]*i32[^}]*\} \{ ptr (@__this_module|null), )" | sed -E "s/^@([^ ]+) = [^{]*(constant|global) (%struct\.file_operations) .*/\3/; s/^@([^ ]+) = [^{]*(constant|global) \{ ptr, .*/LITERAL_FOPS/" | sort | uniq -c | sed "s|^|{} |"' < "$1" >> "$2"
}

# --- stage 3: the original analysis scripts, run in the restored original folders ---
analyses(){
  need_rerun
  links
  say "3) analyses (original scripts, run in $NOSAND, $PASSD, $FINS, $EPID, $SPD as restored by setup.py layout)"
  export PATH=$FPEA_LLVM16:$PATH

  say "   3-1 simple hit rate → $NOSAND/hitfull_<v>.json"
  (
    cd $PASSD && for v in 5.17.11 5.19.17 6.9 7.1.4 7.1.4-norand; do
      case $v in
        5.17.11) T=$FPEA_SRC14;;
        5.19.17) T=$FPEA_BC_519;;
        6.9) T=$FPEA_BC_69;;
        7.1.4) T=$FPEA_BC_714;;
        *) T=$FPEA_BC_714N;;
      esac
      python3 hitrate_full.py $v $T
    done
    python3 hitrate_full.py 5.17.11-llvm16 $FPEA_BC16
  ) >> $NOSAND/hitfull.log 2>&1

  say "   3-2a header offset → $EPID/handler_offset.json (input of semantic_hit.py; it reads only kernel source headers, so it is built before 3-2. The missing ordering was found in the 2026-10-27 new-machine reproduction)"
  (cd $EPID && python3 handler_offset.py > handler_offset.log 2>&1) \
    || say "   warning: handler_offset.py failed — the 3-2 semantic hit rate will be empty"

  say "   3-2 semantic hit rate, named/literal, placeholder units, version aggregation, per-kind loss"
  (
    cd $SPD \
      && bash semantic_hit_all.sh \
      && bash literal_struct_scan.sh \
      && bash placeholder_scan.sh \
      && python3 aggregate_versions.py \
      && python3 kind_drift.py
  ) > $L/analyses_sp.log 2>&1
  lit16_scan $FPEA_OUT/list_nosan16.txt $SPD/lit16_nosan16-5.17.11.txt
  lit16_scan $FPEA_OUT/list_7.1.4-norand.txt $SPD/lit16_7.1.4-norand.txt
  lit16_scan $FPEA_OUT/list_7.1.4.txt $SPD/lit16s_7.1.4.txt
  cp $SPD/lit_*.txt $SPD/lit16*.txt $FINS/

  say "   3-3 UAF subset, C2 evidence, link-layer aggregation (analyze3), typed comparison"
  (cd $FINS && python3 uaf_subset_unit.py) > $L/uaf_subset.log 2>&1
  (
    cd $PASSD \
      && python3 c2_evidence.py \
      && python3 analyze3.py > analyze3.log \
      && cp analyze3.json $NOSAND/ \
      && bash typed_cmp.sh > typed_cmp.log
  ) 2>&1 | tee -a $L/run_all.log

  say "   3-4 link-layer behaviour classification (behavior/atfinal/decomp/fp_audit/fp_refine)"
  (
    cd $NOSAND \
      && python3 behavior.py > behavior.log \
      && python3 atfinal.py > atfinal.log \
      && python3 decomp.py > decomp.log \
      && python3 fp_audit.py > fp_audit.log \
      && python3 fp_refine.py > fp_refine.log
  ) 2>&1 | tee -a $L/run_all.log

  say "   3-5 header offset, Introduction statistics, contamination-filter validation (struct_drift_full only when the KASAN 'full' tree exists)"
  # filter_validate.py samples 400 modules from the measurement server's KASAN/UBSAN + KCFLAGS=-g
  # debug build ($HOME/kernel/linux-5.17.11, which has DISubprogram). The artifact recipe does not
  # build that tree (setup.py layout links that path to the nosan tree) and the sample depends on
  # os.walk order, so without a debug tree the stored copy is used.
  # (2026-10-27 new-machine reproduction: run on the nosan tree there is no DISubprogram, all 6080
  # functions came out as 'debug-only contaminated' and verify broke)
  DBGBC=$(find $HOME/kernel/linux-5.17.11/drivers -name '*.o.bc' 2>/dev/null | head -1)
  if [ -n "$DBGBC" ] && $FPEA_DIS14 -o - "$DBGBC" 2>/dev/null | grep -q DISubprogram; then
    FV="python3 filter_validate.py > filter_validate.log"
  else
    FV="echo 'filter_validate: no debug (-g) build tree — using the stored copy'; cp $R/data/epi/filter_validate.json $R/data/epi/filter_validate.log ."
  fi
  # the struct_drift_full line runs even when the first chain fails (newline, not &&)
  (
    cd $EPID \
      && python3 handler_offset.py > handler_offset.log \
      && python3 intro_stats.py > intro_stats.log \
      && eval "$FV"
    [ -d $HOME/linux_bc/linux-5.18-full ] \
      && python3 struct_drift_full.py > struct_drift_full.log \
      || echo "struct_drift_full: no 'full' tree — using the stored copy"
  ) 2>&1 | tee -a $L/run_all.log

  say "   3-6 placeholder trigger experiment (recompilation with the clang 14.0.6 release) → $FIN/placeholder_trigger.log"
  (
    cd $FINS \
      && python3 placeholder_trigger.py > $FIN/placeholder_trigger.log 2>&1
    python3 placeholder_trigger_hdr.py > $FIN/placeholder_trigger_hdr.log 2>&1
  ) || true
}

# --- stage 4a: reference-set sampling (new sample next to the preserved original) ---
sample(){
  need_rerun
  links
  say "4a) reference-set sampling (seed 517) — for reference only. The original sample with the expert verdicts ($PASSD/gt_*.json) is preserved; a new one is made in $FPEA_WORK/sample_rerun"
  D=$FPEA_WORK/sample_rerun
  mkdir -p $D
  cp $PASSD/sample_gt_unit.py $D/
  (cd $D && python3 sample_gt_unit.py) > $L/sample.log 2>&1
  # compare the new sample with the preserved original
  python3 - "$D/gt_sample_unit.json" "$PASSD/gt_sample_unit.json" <<'PY'
import json
import sys

a, b = [json.load(open(p)) for p in sys.argv[1:3]]
print('positives 255 identical:', a['pos'] == b['pos'],
      ' negatives 200 identical:', a['neg'] == b['neg'],
      '(negatives depend on multiprocessing order and may differ)')
PY
}

# --- stage 5: top-caller filter pilot ---
pilots(){
  need_rerun
  links
  say "5) pilot: top-caller filter (455 cases) → $FIN/tca_pilot.log, tca_pilot_rows.json"
  (
    cd $FINS \
      && python3 tca_pilot.py > $FIN/tca_pilot.log 2>&1 \
      && cp pilot_rows.json $FIN/tca_pilot_rows.json
  )
}

# --- stage 6: figures (needs the json files that derive copies into $FIN) ---
figures(){
  need_rerun
  say "6) figures → $FIN/figures (fig6/fig7 read the subsystem_ratio/strata_pop.json that derive copies into $FIN, so this runs after derive)"
  for j in subsystem_ratio strata_pop version_results final_result_expert; do
    [ -f $FIN/$j.json ] || { say "   warning: $FIN/$j.json missing — run ./run_all.sh derive first (in the 2026-10-28 run on the reproduction VM ('166') figures ran before derive and silently failed, leaving fig6·fig7 missing)"; return 1; }
  done
  (
    cd $FINS \
      && python3 fig2.py \
      && python3 fig_all.py \
      && python3 fig_all.py ascii
  ) > $L/figures.log 2>&1 \
    || { say "   warning: figure generation failed — $L/figures.log"; return 1; }
  say "   figures $(ls $FIN/figures/*.pdf | wc -l) (pdf/png/svg) + ascii $(ls $FIN/figures/ascii/*.pdf | wc -l)"
}

# --- stage D: derived results (derive_results.py) and, in rerun mode, the metric scripts ---
derive(){
  if [ "$FPEA_MODE" = rerun ]; then
    say "D) regenerate derived results from the re-run outputs and compare with the artifact's stored copies (data/results) → $FPEA_OUTDIR/derive_report.md"
    env -u FPEA_RESULTS python3 $S/derive_results.py | tee -a $L/run_all.log
    cp $FPEA_OUTDIR/{strata_pop,subsystem_ratio,fp_types,link_layer_q15,typed_vs_opaque,randstruct_vs_norand_714}.json $FIN/
    say "   metric scripts: final_calc_expert.py, review_check.py (cwd $FIN)"
    (
      cd $FIN \
        && python3 final_calc_expert.py > final_calc_expert.log \
        && python3 review_check.py > review_check.log
    ) 2>&1 | tee -a $L/run_all.log
  else
    say "D) regenerate derived results from the stored outputs + compare with stored copies → $FPEA_OUTDIR/derive_report.md"
    python3 $S/derive_results.py | tee -a $L/run_all.log
  fi
}

# --- stage V: compare the paper numbers (verify_numbers.py) ---
# verify_env: prints the `env ...` prefix for verify_numbers.py. In rerun mode the artifact data/
# variables are unset so that the original layout is read.
verify_env(){
  if [ "$FPEA_MODE" = rerun ]; then
    echo env -u FPEA_RESULTS -u FPEA_DATA FPEA_FINAL=$FIN FPEA_NOSAN=$NOSAND FPEA_PASS=$PASSD \
      FPEA_EPI=$EPID FPEA_EXPERT=$HOME/fpea_gt/expert_pkg
  else
    echo env
  fi
}
verify(){
  say "V) compare paper numbers (light, $FPEA_MODE mode) → $L/verify_report.md"
  $(verify_env) python3 $S/verify_numbers.py \
    --out $L/verify_report.md --json $L/verify_values.json | tee -a $L/run_all.log
}
verify_heavy(){
  say "V) compare paper numbers (heavy: including IR re-interpretation, $FPEA_MODE mode) → $L/verify_report.md"
  $(verify_env) python3 $S/verify_numbers.py --heavy \
    --out $L/verify_report.md --json $L/verify_values.json | tee -a $L/run_all.log
}

# --- stage dispatcher ---
case $stage in
  derive) derive; verify;;
  verify) verify;;
  verify-heavy) verify_heavy;;
  build-kernels) build_kernels;;
  build-tools) build_tools;;
  run-fpea) run_fpea;;
  analyses) analyses;;
  sample) sample;;
  pilots) pilots;;
  figures) figures;;
  all) build_kernels; build_tools; run_fpea; analyses; pilots; derive; figures; verify_heavy;;
  *) echo "unknown stage $stage"; exit 1;;
esac
say "done: $stage"

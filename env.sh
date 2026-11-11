# FPEA reproduction environment variables, read by run_all.sh and scripts/*.py (sourced, not run).
# Nothing here depends on where the checkout lives or on the user name: every variable keeps a
# value already in the environment (`FPEA_X="${FPEA_X:-default}"`), so overrides can be exported
# before sourcing or written into env.local.sh (created by setup.py layout, sourced below), and
# every default is derived from two roots:
#   FPEA_REPRO  the checkout (the folder containing this file)
#   FPEA_HOME   the root of the original measurement layout (rerun/, linux_bc/, fpea_gt/final,
#               epi_regfn/, kernel/, llvm/, llvm-14.0.7/, fpea_work/, tmp/); default
#               $FPEA_REPRO/work. On the measurement server these folders lived directly under
#               the home directory, so FPEA_HOME=$HOME reproduces that layout; a reproduction can
#               put the ~70 GB of build trees on another disk with FPEA_HOME=/big/disk/fpea.
#   FPEA_TMP    the fixed-name files of the original session (units.txt, u_fpea, fpea_out, …,
#               originally under /tmp); default $FPEA_HOME/tmp.
#
# Sections, in the order the variables are set (later lines reference earlier ones):
#   1. roots                    FPEA_REPRO, env.local.sh, FPEA_HOME, FPEA_TMP
#   2. shell environment cleanup (LD_LIBRARY_PATH, PATH)
#   3. toolchains               FPEA_LLVM16/14, FPEA_CLANG14_ALT, FPEA_DIS14/16, FPEA_WLLVM,
#                               FPEA_TARBALLS, FPEA_UAFX_TOOL
#   4. bitcode / source trees   FPEA_SRC14, FPEA_BC*, FPEA_LINKBC, FPEA_SRC_RB, FPEA_HDR_SRC_*
#   5. run mode                 FPEA_MODE and the rerun-only variables
#   6. artifact data defaults   FPEA_OUT, FPEA_LINKOUT, FPEA_UNITS, FPEA_DATA, FPEA_RESULTS,
#                               FPEA_OUTDIR, FPEA_NPROC

# --- 1. roots ---
export FPEA_REPRO="${FPEA_REPRO:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
# env.local.sh is written by setup.py layout (FPEA_MODE=rerun, FPEA_HOME, FPEA_TMP, FPEA_WORK);
# it is read first so that the roots it records drive every default below.
[ -f "$FPEA_REPRO/env.local.sh" ] && source "$FPEA_REPRO/env.local.sh"
export FPEA_HOME="${FPEA_HOME:-$FPEA_REPRO/work}"
export FPEA_TMP="${FPEA_TMP:-$FPEA_HOME/tmp}"

# --- 2. shell environment cleanup ---
# The measurement server's ~/.profile puts the lib of llvm-14.0.7 (placeholder experiment) into
# LD_LIBRARY_PATH. Calling Ubuntu clang++-14 in that state loads libclang-cpp 14.0.7 together with
# libLLVM 14.0.0 and dies with "Option 'mc-relax-all' registered more than once" (found 2026-10-22).
# Inside the artifact it is cleared. 14.0.7 need not be on PATH because placeholder_trigger*.py
# calls it directly by absolute path ($FPEA_CLANG14_ALT).
unset LD_LIBRARY_PATH
export PATH="$(echo "$PATH" | tr : '\n' | grep -v 'llvm-14\.0\.7' | paste -sd:)"

# --- 3. original sources and toolchains (stages 0·1: kernel builds, tool build) ---
# FPEA_LLVM16      clang 16.0.6 (opaque pointer), llvm-dis, llvm-link
# FPEA_LLVM14      clang 14 (typed IR) — for the kernel builds
# FPEA_CLANG14_ALT clang-14 14.0.7 — for the placeholder recompilation experiment
# FPEA_DIS14/16    llvm-dis of the two LLVM versions
# FPEA_WLLVM       wllvm, extract-bc (pip --user puts them under the real $HOME/.local/bin)
# FPEA_TARBALLS    linux-{5.17.11,5.19.17,6.9,7.1.4}.tar.xz
# FPEA_UAFX_TOOL   the UAFX authors' original EntryPointIdentifier (linked against LLVM14)
export FPEA_LLVM16="${FPEA_LLVM16:-$FPEA_HOME/llvm/build/bin}"
export FPEA_LLVM14="${FPEA_LLVM14:-/usr/lib/llvm-14/bin}"
export FPEA_CLANG14_ALT="${FPEA_CLANG14_ALT:-$FPEA_HOME/llvm-14.0.7/bin}"
export FPEA_DIS14="${FPEA_DIS14:-/usr/bin/llvm-dis-14}"
export FPEA_DIS16="${FPEA_DIS16:-$FPEA_LLVM16/llvm-dis}"
export FPEA_WLLVM="${FPEA_WLLVM:-$HOME/.local/bin}"
export FPEA_TARBALLS="${FPEA_TARBALLS:-$FPEA_HOME/rerun/src}"
export FPEA_UAFX_TOOL="${FPEA_UAFX_TOOL:-$FPEA_REPRO/tool/uafx/entry_point_handler_orig}"

# --- 4. bitcode trees (input of stage 2; built by stage 0) ---
# FPEA_SRC14       5.17.11 clang14 nosan, units = drivers/**/.name.o.bc (hidden names)
# FPEA_BC16        5.17.11 clang16 nosan units
# FPEA_BC_519/69   5.19.17 / 6.9 clang14 units
# FPEA_BC_714      7.1.4 clang16, RANDSTRUCT_FULL (allmodconfig default)
# FPEA_BC_714N     7.1.4 clang16, RANDSTRUCT_NONE (values used in the paper body)
# FPEA_LINKBC      link layer (modules via llvm-link)
# FPEA_SRC_RB      5.19.17/6.9/7.1.4 build trees (.cmd files; placeholder experiment)
# FPEA_HDR_SRC_*   the 4 source trees for header parsing by handler_offset.py
export FPEA_SRC14="${FPEA_SRC14:-$FPEA_HOME/rerun/nosan/src14/linux-5.17.11}"
export FPEA_BC16="${FPEA_BC16:-$FPEA_HOME/linux_bc/clean-nosan16-5.17.11}"
export FPEA_BC_519="${FPEA_BC_519:-$FPEA_HOME/linux_bc/nosan-rb-5.19.17}"
export FPEA_BC_69="${FPEA_BC_69:-$FPEA_HOME/linux_bc/nosan-rb-6.9}"
export FPEA_BC_714="${FPEA_BC_714:-$FPEA_HOME/linux_bc/nosan-rb-7.1.4}"
export FPEA_BC_714N="${FPEA_BC_714N:-$FPEA_HOME/linux_bc/nosan-rb-7.1.4-norand}"
export FPEA_LINKBC="${FPEA_LINKBC:-$FPEA_HOME/linux_bc/linked-nosan14-5.17.11}"
export FPEA_SRC_RB="${FPEA_SRC_RB:-$FPEA_HOME/rerun/nosan/src_rb}"
export FPEA_HDR_SRC_517="${FPEA_HDR_SRC_517:-$FPEA_HOME/kernel/linux-5.17.11}"
export FPEA_HDR_SRC_519="${FPEA_HDR_SRC_519:-$FPEA_HOME/kbuild/src/linux-5.19.17}"
export FPEA_HDR_SRC_69="${FPEA_HDR_SRC_69:-$FPEA_HOME/kbuild/src/linux-6.9}"
export FPEA_HDR_SRC_714="${FPEA_HDR_SRC_714:-$FPEA_HOME/linux-7.1.4}"

# --- 5. run mode ---
# artifact (default): derive/verify read only the stored outputs under data/. Stages that would
#          change the stored outputs (build-kernels, run-fpea, analyses, …) are refused.
# rerun:   writes new outputs into the original layout restored by setup.py ($FPEA_HOME/rerun,
#          $FPEA_HOME/fpea_gt/final, $FPEA_HOME/epi_regfn, …) and into the work folder
#          $FPEA_WORK. setup.py layout writes FPEA_MODE=rerun into env.local.sh (read in
#          section 1), so it normally need not be set by hand.
# The rerun block must stay above section 6: it gives FPEA_OUT/LINKOUT/UNITS/RESULTS their
# work-folder values first, so that the artifact defaults below do not apply.
export FPEA_MODE="${FPEA_MODE:-artifact}"
if [ "$FPEA_MODE" = rerun ]; then
  # FPEA_WORK plays the role of the original session scratchpad:
  # rf_*/rw_*/list_*/lit_*/ph_* and link/
  export FPEA_WORK="${FPEA_WORK:-$FPEA_HOME/fpea_work}"
  export FPEA_SCRATCH="${FPEA_SCRATCH:-$FPEA_WORK}"
  export FPEA_OUT="${FPEA_OUT:-$FPEA_WORK}"
  export FPEA_LINKOUT="${FPEA_LINKOUT:-$FPEA_WORK/link/fpea_out}"
  export FPEA_UNITS="${FPEA_UNITS:-$FPEA_WORK/list_5.17.11.txt}"
  # original folders of the analysis scripts (FPEA_FIN = where they write their results)
  export FPEA_FIN="${FPEA_FIN:-$FPEA_HOME/fpea_gt/final}"
  export FPEA_NOSAN_DIR="${FPEA_NOSAN_DIR:-$FPEA_HOME/rerun/nosan}"
  export FPEA_PASS_DIR="${FPEA_PASS_DIR:-$FPEA_HOME/rerun/fpea_pass}"
  export FPEA_EPI_DIR="${FPEA_EPI_DIR:-$FPEA_HOME/epi_regfn}"
  export FPEA_RESULTS="${FPEA_RESULTS:-$FPEA_FIN}"
fi

# --- 6. FPEA/UAFX outputs and results (artifact defaults; already set above in rerun mode) ---
# FPEA_OUT      rf_<V>/ rw_<V>/ list_<V>.txt rf_nosan16/ (input of stage 3; produced by stage 2,
#               a copy is kept in the artifact's data/fpea_out)
# FPEA_LINKOUT  link-layer fpea16 output
# FPEA_UNITS    the 5.17.11 unit list
# FPEA_DATA     the artifact's data/ folder
# FPEA_RESULTS  stored result json (comparison target)
# FPEA_OUTDIR   regenerated results
# FPEA_NPROC    xargs parallelism of the unit runs
export FPEA_OUT="${FPEA_OUT:-$FPEA_REPRO/data/fpea_out}"
export FPEA_LINKOUT="${FPEA_LINKOUT:-$FPEA_REPRO/data/link/fpea_out}"
export FPEA_UNITS="${FPEA_UNITS:-$FPEA_OUT/list_5.17.11.txt}"
export FPEA_DATA="${FPEA_DATA:-$FPEA_REPRO/data}"
export FPEA_RESULTS="${FPEA_RESULTS:-$FPEA_REPRO/data/results}"
export FPEA_OUTDIR="${FPEA_OUTDIR:-$FPEA_REPRO/out}"
export FPEA_NPROC="${FPEA_NPROC:-14}"

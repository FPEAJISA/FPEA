#!/usr/bin/env bash
# Build one kernel tree and collect its per-unit bitcode. Unifies the recipes of the original
# build_nosan.sh / rebuild_versions.sh / build_71_norand.sh (not included in the public artifact)
# on the env.sh paths.
#   build_kernel.sh <5.17.11|5.19.17|6.9|7.1.4> <14|16> [norand|dbg] [--config-only]
#   dbg (5.17.11/14 only): allmodconfig as is (KASAN/UBSAN/KCOV on) + KCFLAGS=-g debug build.
#   Recipe of the measurement server's ~/kernel/linux-5.17.11 (2026-08-13; the only .config
#   differences are sanitizer-dependent options), which filter_validate.py (3.4 contamination-filter
#   validation) reads for DISubprogram. No collection and no sanitizer gate; after the build the
#   link at that path is pointed to this tree.
# Recipe: clean tarball extraction -> allmodconfig
#         -> KASAN/UBSAN/KCSAN/KCOV/GCOV/KMSAN off (norand: RANDSTRUCT_NONE) -> olddefconfig
#         -> make CC=wllvm -k drivers/ -> collect .name.o.bc as name.o.bc
#         -> gate (duplicates 0, llvm-link products 0, asan symbols 0)
# Combinations used for the measurements: 5.17.11/14, 5.17.11/16, 5.19.17/14, 6.9/14,
#         7.1.4/16 (RANDSTRUCT_FULL), 7.1.4/16 norand
set -u
cd "$(dirname "$0")/.."
source ./env.sh

# ---------------------------------------------------------------- helpers
# say MSG: timestamped, labelled line to stdout, the per-build log and nosan/all.log
say(){
  echo "[$(date '+%m/%d %H:%M:%S')] [$LBL] $*" | tee -a $LOG | tee -a $NOSAN/all.log
}

# ---------------------------------------------------------------- arguments and paths
# parse_args "$@": V (kernel version), TC (14|16), TAG (""|norand|dbg), CFGONLY (0|1)
parse_args(){
  V=$1
  TC=$2
  TAG=""
  CFGONLY=0
  for a in "${@:3}"; do
    case $a in
      norand) TAG=norand;;
      dbg) TAG=dbg;;
      --config-only) CFGONLY=1;;
    esac
  done
  if [ "$TAG" = dbg ]; then
    [ "$1" = 5.17.11 ] && [ "$2" = 14 ] || {
      echo "dbg is only for 5.17.11 14"
      exit 1
    }
  fi
}

# set_paths: CP (clang folder), DIS16, SRC (build tree), OUT (bitcode folder), LBL, LOG
set_paths(){
  NOSAN=$FPEA_HOME/rerun/nosan
  mkdir -p $NOSAN $FPEA_HOME/linux_bc
  case $TC in
    14) CP=$FPEA_LLVM14;;
    16) CP=$FPEA_LLVM16;;
    *)
      echo "TC must be 14|16"
      exit 1
      ;;
  esac
  DIS16=$FPEA_DIS16
  if [ "$TAG" = dbg ]; then
    SRC=$FPEA_HOME/rerun/dbg/src$TC/linux-$V
    OUT=""
    LBL="dbg$TC"
    LOG=$NOSAN/build_dbg$TC.log
  elif [ "$V" = 5.17.11 ]; then
    SRC=$FPEA_HOME/rerun/nosan/src$TC/linux-$V
    OUT=$FPEA_HOME/linux_bc/clean-nosan$TC-$V
    LBL="llvm$TC"
    LOG=$NOSAN/build_$TC.log
  else
    SRC=$FPEA_SRC_RB/linux-$V${TAG:+-$TAG}
    OUT=$FPEA_HOME/linux_bc/nosan-rb-$V${TAG:+-$TAG}
    LBL="rb-$V${TAG:+-$TAG}"
    LOG=$NOSAN/rebuild_$V${TAG:+_$TAG}.log
  fi
}

# check_tools: clang, the kernel tarball (TB) and wllvm must be present
check_tools(){
  [ -x $CP/clang ] || { say "no clang in $CP ABORT"; exit 1; }
  TB=$FPEA_TARBALLS/linux-$V.tar.xz
  [ -f $TB ] || { say "tarball missing $TB ABORT"; exit 1; }
  command -v wllvm >/dev/null || export PATH=$FPEA_WLLVM:$PATH
  command -v wllvm >/dev/null || { say "wllvm missing ABORT"; exit 1; }
}

# skip_if_done: a finished tree (.fpea_build_done) is not rebuilt unless --config-only
skip_if_done(){
  if [ -f $SRC/.fpea_build_done ] && [ $CFGONLY = 0 ]; then
    say "$SRC already done — skipping (delete .fpea_build_done to redo)"
    exit 0
  fi
}

# ---------------------------------------------------------------- phases
# 1) clean source: extract the tarball into a fresh SRC
prepare_source(){
  rm -rf "$SRC"
  mkdir -p "$(dirname $SRC)"
  T=$(mktemp -d "$(dirname $SRC)/.x_XXXX")
  tar xf $TB -C $T || { say "tar failed ABORT"; exit 1; }
  mv $T/linux-$V "$SRC"
  rmdir $T
  say "source prepared $SRC, clang: $($CP/clang --version | head -1)"
}

# 2) config: allmodconfig, sanitizers off (except dbg), olddefconfig, then check the result.
#    Leaves the shell inside SRC. Exits after the config gate with --config-only.
configure(){
  export LLVM_COMPILER=clang LLVM_CC_NAME=clang LLVM_COMPILER_PATH=$CP
  cd $SRC
  make CC=wllvm HOSTCC=$CP/clang allmodconfig > $NOSAN/cfg_$LBL.log 2>&1 || { say "allmodconfig failed ABORT"; exit 1; }
  [ "$TAG" = dbg ] || ./scripts/config --disable KASAN --disable UBSAN --disable KCSAN --disable KCOV --disable GCOV_KERNEL --disable KMSAN
  [ "$TAG" = norand ] && ./scripts/config --disable RANDSTRUCT_FULL --disable RANDSTRUCT_PERFORMANCE --enable RANDSTRUCT_NONE
  make CC=wllvm HOSTCC=$CP/clang olddefconfig >> $NOSAN/cfg_$LBL.log 2>&1
  # S: the sanitizer options still enabled
  S=$(grep -E '^CONFIG_(KASAN|UBSAN|KCSAN|KCOV|GCOV_KERNEL)=y' .config | tr '\n' ' ')
  if [ "$TAG" = dbg ]; then
    grep -q '^CONFIG_KASAN=y' .config \
      && grep -q '^CONFIG_UBSAN=y' .config \
      && grep -q '^CONFIG_KCOV=y' .config \
      || { say "dbg but KASAN/UBSAN/KCOV are not enabled ABORT"; exit 1; }
    say "config OK(dbg): modules $(grep -c '=m$' .config), sanitizers on: $S KCFLAGS=-g"
    [ $CFGONLY = 1 ] && { say "config-only done"; exit 0; }
  else
    [ -n "$S" ] && { say "sanitizer still enabled: $S ABORT"; exit 1; }
    [ "$TAG" = norand ] && {
      grep -q '^CONFIG_RANDSTRUCT_NONE=y' .config || { say "failed to set RANDSTRUCT_NONE ABORT"; exit 1; }
    }
    say "config OK: modules $(grep -c '=m$' .config), sanitizers all off, $(grep -E '^CONFIG_RANDSTRUCT_(NONE|FULL)=y' .config | tr '\n' ' ')CC=$(grep CONFIG_CC_VERSION_TEXT .config)"
    [ $CFGONLY = 1 ] && { say "config-only done"; exit 0; }
  fi
}

# 2b) With RANDSTRUCT_FULL, plant the seed used for the measurement. Without the seed file
#     scripts/gen-randstruct-seed.sh makes a new one from /dev/urandom, struct layout and inlining
#     decisions change and the defined-function count is off by a few (2026-10-27 reproduction on
#     another machine: 301301 vs measured 301306; the FPEA count was identical). kbuild's if_changed
#     looks at .randstruct.seed.cmd and mtimes, so the .cmd and hash.h are placed too and touched.
#     Sets SEEDSRC (the seed folder, or "" when no stored seed is used).
install_randstruct_seed(){
  SEEDSRC=""
  if grep -q '^CONFIG_RANDSTRUCT_FULL=y' .config; then
    SEEDSRC=$FPEA_REPRO/data/randstruct_$V
    if [ -f $SEEDSRC/randstruct.seed ]; then
      mkdir -p scripts/basic include/generated
      cp $SEEDSRC/randstruct.seed scripts/basic/randstruct.seed
      cp $SEEDSRC/.randstruct.seed.cmd scripts/basic/.randstruct.seed.cmd
      cp $SEEDSRC/randstruct_hash.h include/generated/randstruct_hash.h
      touch scripts/basic/randstruct.seed include/generated/randstruct_hash.h
      say "RANDSTRUCT seed installed: $(cut -c1-16 scripts/basic/randstruct.seed)… (data/randstruct_$V)"
    else
      say "warning: RANDSTRUCT_FULL but no stored seed ($SEEDSRC) — building with a new seed, the defined-function count may differ"
      SEEDSRC=""
    fi
  fi
}

# 3) build (drivers/ only, -k); NO / NB = number of .o / wllvm .o.bc files produced
build_drivers(){
  say "build start -j$FPEA_NPROC"
  KCF=""
  [ "$TAG" = dbg ] && KCF="KCFLAGS=-g"
  make CC=wllvm HOSTCC=$CP/clang $KCF -j$FPEA_NPROC -k drivers/ > $NOSAN/make_$LBL.log 2>&1
  NO=$(find drivers -name '*.o' | wc -l)
  NB=$(find drivers -name '.*.o.bc' | wc -l)
  say "build done: .o $NO, .bc(wllvm) $NB"
  if [ -n "$SEEDSRC" ]; then
    cmp -s $SEEDSRC/randstruct.seed scripts/basic/randstruct.seed \
      && say "RANDSTRUCT seed kept (not regenerated during the build)" \
      || say "warning: the RANDSTRUCT seed changed during the build — expect the defined-function comparison to fail"
  fi
  [ "$NO" -lt 1000 ] && { say "too few .o ABORT"; exit 1; }
}

# dbg gate: all 20 sampled units have DISubprogram (debug info) and asan/ubsan symbols (confirms a
# sanitizer build). No collection (filter_validate.py reads the .bc inside the tree).
dbg_gate(){
  D=0
  A=0
  for f in $(find drivers -name '.*.o.bc' | shuf -n 20 --random-source=/dev/zero); do
    t=$($DIS16 -o - "$f" 2>/dev/null)
    echo "$t" | grep -q DISubprogram && D=$((D+1))
    echo "$t" | grep -qE '@(__asan_|__ubsan_|asan\.)' && A=$((A+1))
  done
  say "gate(dbg): of 20 sampled units DISubprogram present $D, asan/ubsan symbols present $A (should be close to 20 / 20; the measurement server tree has 15,370 .o.bc)"
  [ "$D" -ge 18 ] || { say "no debug info ABORT"; exit 1; }
}

# dbg: point $FPEA_HOME/kernel/linux-5.17.11 (read by filter_validate.py and handler_offset.py) to SRC,
# unless it is a real directory (the original tree of the measurement server)
link_debug_tree(){
  LK=$FPEA_HOME/kernel/linux-5.17.11
  if [ -L $LK ] || [ ! -e $LK ]; then
    rm -f $LK
    mkdir -p $FPEA_HOME/kernel
    ln -s $SRC $LK
    say "$LK → $SRC (path read by filter_validate.py and handler_offset.py)"
  else
    say "$LK is a real directory (original tree of the measurement server) — link left unchanged"
  fi
}

# 4) collection — only the .name.o.bc files written by wllvm; extract-bc is not used
collect_bitcode(){
  rm -rf $OUT
  mkdir -p $OUT
  n=0
  while IFS= read -r f; do
    d=$(dirname "$f")
    b=$(basename "$f")
    mkdir -p "$OUT/$d"
    cp "$f" "$OUT/$d/${b#.}"
    n=$((n+1))
  done < <(find drivers -name '.*.o.bc')
  say "collected $n → $OUT"
}

# 5) gate: duplicate paths, llvm-link products, KASAN wrappers and asan/ubsan symbols must all be 0
#    (40 units sampled with a fixed random source)
gate(){
  DUP=$(cd $OUT && find . -name '*.o.bc' \
    | sort \
    | uniq -d \
    | wc -l)
  L=0
  W=0
  A=0
  for f in $(find $OUT -name '*.o.bc' | shuf -n 40 --random-source=/dev/zero); do
    t=$($DIS16 -o - "$f" 2>/dev/null)
    echo "$t" | grep -m1 source_filename | grep -q llvm-link && L=$((L+1))
    W=$((W + $(echo "$t" | grep -cE '^@[^=]+= [^{]*\{ %struct\.[A-Za-z0-9_.]+, \[[0-9]+ x i8\] \}')))
    A=$((A + $(echo "$t" | grep -cE '@(__asan_|__ubsan_|asan\.)')))
  done
  say "gate: duplicate paths=$DUP llvm-link=$L KASAN wrappers=$W asan/ubsan symbols=$A (all must be 0)"
  [ "$DUP" -eq 0 ] && [ "$L" -eq 0 ] && [ "$W" -eq 0 ] && [ "$A" -eq 0 ] \
    || { say "gate failed ABORT"; exit 1; }
}

# norand: show the first field of spidev_fops (a plain layout proves RANDSTRUCT_NONE took effect)
show_spidev_fops(){
  o=$($DIS16 -o - $OUT/drivers/spi/spidev.o.bc 2>/dev/null \
    | grep -E '^@spidev_fops' \
    | grep -o -E '\{ ptr [^,]*' \
    | head -1)
  say "spidev_fops first field: $o"
}

# 6) 5.17.11/14: list of .o without bc (Ch. 4) — .o files with no matching .name.o.bc
list_missing_bc(){
  mkdir -p $FPEA_HOME/fpea_gt/final
  find drivers -name '*.o' | while read -r o; do
    [ -f "$(dirname $o)/.$(basename $o).bc" ] || echo "$o"
  done > $FPEA_HOME/fpea_gt/final/missing_bc_objects.txt
  say ".o without bc $(wc -l < $FPEA_HOME/fpea_gt/final/missing_bc_objects.txt) → fpea_gt/final/missing_bc_objects.txt"
}

# ---------------------------------------------------------------- main flow
parse_args "$@"
set_paths
check_tools
skip_if_done
prepare_source
configure
install_randstruct_seed
build_drivers
if [ "$TAG" = dbg ]; then
  dbg_gate
  link_debug_tree
  touch $SRC/.fpea_build_done
  say "done"
  exit 0
fi
collect_bitcode
gate
if [ "$TAG" = norand ]; then
  show_spidev_fops
fi
if [ "$V" = 5.17.11 ] && [ "$TC" = 14 ]; then
  list_missing_bc
fi
touch $SRC/.fpea_build_done
say "done"

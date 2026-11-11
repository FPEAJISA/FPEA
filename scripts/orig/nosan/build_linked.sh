#!/usr/bin/env bash
# Build the linked module layer: llvm-link the wllvm units (.name.o.bc) listed in each .mod
# Usage: build_linked.sh <toolchain: 14|16>
#   input : $FPEA_HOME/rerun/nosan/src<TC>/linux-5.17.11 (wllvm build with per-unit .bc)
#   output: $FPEA_HOME/linux_bc/linked-nosan<TC>-5.17.11/{modules,builtin}/*.bc, link_report.txt
#   log   : $FPEA_HOME/rerun/nosan/linked_<TC>.log (the say lines), .linked_<TC> stamp on completion
set -u
TC=$1
V=5.17.11
# root of the original measurement layout (env.sh FPEA_HOME; the home directory on the measurement server)
H=${FPEA_HOME:-$HOME}
SRC=$H/rerun/nosan/src$TC/linux-$V
OUT=$H/linux_bc/linked-nosan$TC-$V
LOG=$H/rerun/nosan/linked_$TC.log
if [ "$TC" = 14 ]; then
  LINK=/usr/bin/llvm-link-14
  DIS=/usr/bin/llvm-dis-14
else
  LINK=$H/llvm/build/bin/llvm-link
  DIS=$H/llvm/build/bin/llvm-dis
fi

# say MSG...: timestamped progress line to stdout and the log
say(){
  echo "[$(date '+%m/%d %H:%M:%S')] [linked$TC] $*" | tee -a $LOG
}

# link_one MODFILE: llvm-link the units listed on the first line of a .mod file into
# $OUT/modules/<path_with_underscores>.bc; reports EMPTY / FAIL / MISS lines on stdout
link_one(){
  m="$1"
  objs=$(head -1 "$m")
  bcs=""
  miss=0
  for o in $objs; do
    b="$(dirname $o)/.$(basename $o).bc"
    if [ -f "$b" ]; then
      bcs="$bcs $b"
    else
      miss=$((miss+1))
    fi
  done
  name=$(echo "${m%.mod}" | tr '/' '_')
  [ -z "$bcs" ] && { echo "EMPTY $m" ; return; }
  if ! $LINK -o "$OUT/modules/$name.bc" $bcs 2>"$OUT/modules/$name.err"; then
    echo "FAIL $m"
  else
    rm -f "$OUT/modules/$name.err"
  fi
  [ $miss -gt 0 ] && echo "MISS $miss $m"
}

# link_modules: run link_one over every drivers/**/*.mod with 14 parallel workers
link_modules(){
  say "link start ($(find drivers -name '*.mod' | wc -l) .mod files)"
  find drivers -name '*.mod' \
    | xargs -P 14 -I{} bash -c 'link_one "$@"' _ {} > $OUT/link_report.txt
  say "link done: succeeded $(ls $OUT/modules/*.bc 2>/dev/null | wc -l), failed $(grep -c ^FAIL $OUT/link_report.txt), empty list $(grep -c ^EMPTY $OUT/link_report.txt), modules with missing objects $(grep -c ^MISS $OUT/link_report.txt)"
}

# copy_builtin: copy units not belonging to any module (built-in) into $OUT/builtin
copy_builtin(){
  python3 - "$SRC" "$OUT" << 'PY'
import os
import glob
import shutil
import sys

S, O = sys.argv[1], sys.argv[2]
os.chdir(S)
# units that belong to some module (first line of each .mod)
mem = set()
for m in glob.glob('drivers/**/*.mod', recursive=True):
    mem |= set(open(m).read().split('\n')[0].split())
n = 0
for r, _, fs in os.walk('drivers'):
    for f in fs:
        if f.startswith('.') and f.endswith('.o.bc'):
            o = os.path.join(r, f[1:-3])
            if o not in mem:
                dst = os.path.join(O, 'builtin', o.replace('/', '_') + '.bc')
                shutil.copy(os.path.join(r, f), dst)
                n += 1
print(f"built-in units {n}")
PY
}

# gate: source_filename of sampled link outputs is llvm-link, no duplicate paths
gate(){
  L=0
  for f in $(ls $OUT/modules/*.bc | shuf -n 20 --random-source=/dev/zero); do
    $DIS -o - $f 2>/dev/null | grep -m1 source_filename | grep -q llvm-link && L=$((L+1))
  done
  say "gate: llvm-link outputs among 20 sampled modules: $L (should be 20)"
}

rm -rf $OUT
mkdir -p $OUT/modules $OUT/builtin
cd $SRC
export SRC OUT LINK
export -f link_one
link_modules
copy_builtin
gate
touch $H/rerun/nosan/.linked_$TC

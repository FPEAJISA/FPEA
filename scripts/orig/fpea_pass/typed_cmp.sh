#!/usr/bin/env bash
# Typed-IR comparison: run the LLVM14 (typed pointer) FPEA tool over the linked nosan14
# tree and compare its entry-point sets with the LLVM16 (opaque pointer) results in
# $FPEA_TMP/fpea_out.  Prints a two-line summary plus up to 5 differing files.
# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
H=${FPEA_HOME:-$HOME}
T=${FPEA_TMP:-/tmp}
O=$H/linux_bc/linked-nosan14-5.17.11
mkdir -p $T/fpea14_out

# Run fpea14 on every unit in parallel (the sh -c template is kept verbatim apart from the roots).
find $O/modules $O/builtin -name '*.bc' \
  | xargs -P 14 -I{} sh -c 'f="{}"; '"$H"'/rerun/fpea_pass/fpea14 "$f" "'"$T"'/fpea14_out/$(echo $f | tr / _).json" 2>/dev/null'

# Compare the typed (fpea14) and opaque (fpea16) entry-point sets per unit.
T="$T" python3 - << 'PY'
import glob
import json
import os

TYPED_GLOB = os.environ['T'] + '/fpea14_out/*.json'
OPAQUE_DIR = os.environ['T'] + '/fpea_out/'


def entry_sets(path):
    """function -> set of signals from one FPEA JSON file."""
    with open(path) as fh:
        return {f: set(s) for f, s in json.load(fh)['entries'].items()}


typed_total = opaque_total = 0
same = differing = 0
only14 = only16 = 0
examples = []
for typed_path in glob.glob(TYPED_GLOB):
    opaque_path = OPAQUE_DIR + os.path.basename(typed_path)
    if not os.path.exists(opaque_path):
        continue
    e14 = entry_sets(typed_path)
    e16 = entry_sets(opaque_path)
    typed_total += len(e14)
    opaque_total += len(e16)
    o1 = set(e14) - set(e16)
    o2 = set(e16) - set(e14)
    only14 += len(o1)
    only16 += len(o2)
    if o1 or o2:
        differing += 1
        if len(examples) < 5:
            examples.append((os.path.basename(typed_path)[-50:], sorted(o1)[:2], sorted(o2)[:2]))
    else:
        same += 1
print(f"  typed (LLVM14 tool) entry points {typed_total}   opaque (LLVM16 tool) {opaque_total}")
print(f"  typed only {only14}   opaque only {only16}"
      f"   files with differing sets {differing} / identical {same}")
for e in examples:
    print("   ", e)
PY

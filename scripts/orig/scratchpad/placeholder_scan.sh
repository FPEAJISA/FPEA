#!/usr/bin/env bash
# Per unit, whether the %struct.file_operations named type contains a {}* placeholder
# (typed IR, clang14).  Output: $SP/ph_<version>.txt (`<unit> PLACEHOLDER|CLEAN` per unit),
# per-version counts in $SP/placeholder_scan.log.
# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
H=${FPEA_HOME:-$HOME}
T=${FPEA_TMP:-/tmp}
SP=${FPEA_WORK:-$T/scratchpad}

# Patterns over the textual IR, spliced into the per-unit sh -c template below, which must
# stay byte-identical to the original one-liner (patterns verbatim, inner quotes escaped).
# the named type definition line of file_operations
TYPE_LINE='^%struct\.file_operations = type'
# a {}* placeholder field inside it
PLACEHOLDER='{\}\*'
# per-unit command run by xargs ({} = unit path)
UNIT_CMD="/usr/bin/llvm-dis-14 -o - \"{}\" 2>/dev/null | grep -E \"$TYPE_LINE\" | { grep -q \"$PLACEHOLDER\" && echo \"{} PLACEHOLDER\" || echo \"{} CLEAN\"; }"

for V in 5.17.11 5.19.17 6.9; do
  if [ "$V" = "5.17.11" ]; then
    L=$T/units.txt
  else
    L=$SP/list_$V.txt
  fi
  OUT=$SP/ph_$V.txt
  : > $OUT
  xargs -P 14 -I{} sh -c "$UNIT_CMD" < $L >> $OUT
  echo "[$V] $(grep -c PLACEHOLDER $OUT) placeholder / $(grep -c CLEAN $OUT) clean" >> $SP/placeholder_scan.log
done
echo ALLDONE >> $SP/placeholder_scan.log

#!/usr/bin/env bash
# Run semantic_hit.py for the five kernel versions (header column per version; the random
# layout build 7.1.4 uses 'rand'), appending all output to $S/semantic_hit.log.
# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
H=${FPEA_HOME:-$HOME}
T=${FPEA_TMP:-/tmp}
S=${FPEA_WORK:-$T/scratchpad}
LOG=$S/semantic_hit.log
: > $LOG
cd $S

# semantic_hit <version> <bc tree> <header column>: one run, stdout+stderr appended to the log
semantic_hit() {
  python3 semantic_hit.py "$1" "$2" "$3" >> $LOG 2>&1
}

semantic_hit 7.1.4-norand $H/linux_bc/nosan-rb-7.1.4-norand 7.1
semantic_hit 5.17.11 $H/rerun/nosan/src14/linux-5.17.11 5.17
semantic_hit 5.19.17 $H/linux_bc/nosan-rb-5.19.17 5.19
semantic_hit 6.9 $H/linux_bc/nosan-rb-6.9 6.9
semantic_hit 7.1.4 $H/linux_bc/nosan-rb-7.1.4 rand
echo ALLDONE >> $LOG

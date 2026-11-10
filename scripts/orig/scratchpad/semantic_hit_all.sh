#!/usr/bin/env bash
# Run semantic_hit.py for the five kernel versions (header column per version; the random
# layout build 7.1.4 uses 'rand'), appending all output to $S/semantic_hit.log.
S=/tmp/claude-1000/-home-user-fpea-gt/beb7f00d-7da4-4363-8809-fde4eb5531af/scratchpad
LOG=$S/semantic_hit.log
: > $LOG
cd $S

# semantic_hit <version> <bc tree> <header column>: one run, stdout+stderr appended to the log
semantic_hit() {
  python3 semantic_hit.py "$1" "$2" "$3" >> $LOG 2>&1
}

semantic_hit 7.1.4-norand $HOME/linux_bc/nosan-rb-7.1.4-norand 7.1
semantic_hit 5.17.11 $HOME/rerun/nosan/src14/linux-5.17.11 5.17
semantic_hit 5.19.17 $HOME/linux_bc/nosan-rb-5.19.17 5.19
semantic_hit 6.9 $HOME/linux_bc/nosan-rb-6.9 6.9
semantic_hit 7.1.4 $HOME/linux_bc/nosan-rb-7.1.4 rand
echo ALLDONE >> $LOG

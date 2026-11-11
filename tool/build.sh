#!/usr/bin/env bash
# Build the FPEA tool (fpea.cpp) twice, once per LLVM major version:
#   fpea16 — LLVM 16 of $FPEA_LLVM16 (env.sh; the measurement server's source build, a
#            reproduction's apt.llvm.org package; opaque pointers; 5.17.11-clang16 and 7.1.4
#            units, the link layer)
#   fpea14 — the distribution LLVM 14 (typed pointers; the fpea14 link-layer comparison)
# Run from this folder (run_all.sh build-tools does `cd tool && bash build.sh`); any failure
# aborts (set -e). The llvm-config substitutions are deliberately unquoted: each expands to
# several flags.
set -e

# LLVM 16: clang++ and llvm-config of $FPEA_LLVM16 (fallback: the measurement server's path)
LLVM16=${FPEA_LLVM16:-$HOME/llvm/build/bin}
CXX16=$LLVM16/clang++
LC16=$LLVM16/llvm-config
# LLVM 14: the Ubuntu packages (clang++-14, llvm-config-14 on PATH)
CXX14=clang++-14
LC14=llvm-config-14

$CXX16 -O2 fpea.cpp -o fpea16 \
  $($LC16 --cxxflags) $($LC16 --ldflags) \
  $($LC16 --libs core irreader support bitreader asmparser) \
  $($LC16 --system-libs) -fexceptions
$CXX14 -O2 fpea.cpp -o fpea14 \
  $($LC14 --cxxflags) $($LC14 --ldflags) \
  $($LC14 --libs core irreader support bitreader asmparser) \
  $($LC14 --system-libs) -fexceptions
echo "built: fpea16 (opaque), fpea14 (typed)"

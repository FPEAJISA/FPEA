#!/usr/bin/env bash
# Symbol -> defining unit map of the 5.17.11 units (llvm-nm --defined-only, T/t/W/w symbols),
# input of wl_ext.py. One file per unit, then concatenated (the 2026-11-09 version wrote all
# xargs workers into one file and 1,440 lines were interleaved; those garbled lines are what made
# 7 external names look "outside drivers/" and 4 look undefined in the first decomposition).
# Usage: defmap.sh <unit list> <out.tsv.gz>
set -e
LIST=$1; OUT=$2
NM=${FPEA_LLVM14:-/usr/lib/llvm-14/bin}/llvm-nm
T=$(mktemp -d)
xargs -P "${FPEA_NPROC:-14}" -I{} sh -c 'u="{}"; '"$NM"' --defined-only "$u" 2>/dev/null | awk -v u="$u" "\$2 ~ /^[TtWw]$/ {print \$3\"\t\"u}" > "'$T'/$(echo "$u" | tr / _).tsv"' < "$LIST"
cat "$T"/*.tsv | sort | gzip -9 > "$OUT"
rm -rf "$T"
echo "defmap: $(zcat "$OUT" | wc -l) symbols -> $OUT"

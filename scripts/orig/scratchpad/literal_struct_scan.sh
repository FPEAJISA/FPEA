#!/usr/bin/env bash
# Full per-version tally of whether global initializers appear as named structs (%struct.X {)
# or literal structs ({ ...) (rule structs such as file_operations).
# Output: $SP/lit_<version>.txt (one `<unit> <count> <struct|LITERAL_FOPS>` line per tally),
# progress in $SP/literal_struct_scan.log.
SP=/tmp/claude-1000/-home-user-fpea-gt/beb7f00d-7da4-4363-8809-fde4eb5531af/scratchpad

# Regexes over the textual IR (clang14, typed pointers).  They are spliced into the per-unit
# sh -c template below, which must stay byte-identical to the original one-liner: the
# patterns are kept verbatim and the inner double quotes of the template are escaped.
# initializer of a named struct, or of the literal file_operations layout
GREP_INIT='^@[^ ]+ = [^{]*(constant|global) (%struct\.[A-Za-z_0-9]+ \{|\{ %struct\.module\*, i64 \(%struct\.file\*, i64, i32\)\*)'
# reduce the line to the struct name (or to the literal layout prefix)
SED_NAME='s/^@([^ ]+) = [^{]*(constant|global) (%struct\.[A-Za-z_0-9]+|\{ %struct\.module\*, i64 \(%struct\.file\*, i64, i32\)\*).*/\3/'
# name the literal layout
SED_LITERAL='s/^\{ %struct\.module\*.*/LITERAL_FOPS/'
# per-unit command run by xargs ({} = unit path): disassemble, grep, reduce, tally, prefix
UNIT_CMD="/usr/bin/llvm-dis-14 -o - \"{}\" 2>/dev/null | grep -E \"$GREP_INIT\" | sed -E \"$SED_NAME\" | sed -E \"$SED_LITERAL\" | sort | uniq -c | sed \"s|^|{} |\""

for V in 5.17.11 5.19.17 6.9; do
  if [ "$V" = "5.17.11" ]; then
    L=/tmp/units.txt
  else
    L=$SP/list_$V.txt
  fi
  OUT=$SP/lit_$V.txt
  : > $OUT
  xargs -P 14 -I{} sh -c "$UNIT_CMD" < $L >> $OUT
  echo "[$V] done" >> $SP/literal_struct_scan.log
done
echo ALLDONE >> $SP/literal_struct_scan.log

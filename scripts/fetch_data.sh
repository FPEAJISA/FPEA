#!/usr/bin/env bash
# Unpack the bundled data archives (data/archives/{fpea_out,link}.tar.gz) into data/ and verify
# the md5 of every extracted file.
#
#   scripts/fetch_data.sh
#
# data/archives/review_package.tar.gz (the package handed to the expert reviewers) is not needed
# by any script and is left as an archive; see README.md.
# Everything runs inside data/ (set -e: the first failing tar aborts the script).
set -e
R=$(cd "$(dirname "$0")/.." && pwd)
cd "$R/data"

# extract_archives: unpack archives/{fpea_out,link}.tar.gz into data/<name>/; a folder that is
# already populated is left alone
extract_archives(){
  for a in fpea_out link; do
    if [ -d $a ] && [ -n "$(ls $a 2>/dev/null)" ]; then
      echo "data/$a already present — skipping"
      continue
    fi
    echo "extracting data/$a ..."
    tar xzf archives/$a.tar.gz --strip-components=1
  done
}

extract_archives
# the md5 check stays at top level: a failing md5sum must not abort the script (it is the
# left-hand side of the && list, so set -e ignores it)
echo "verifying md5 of extracted files ..."
zcat archives/MANIFEST_data.md5.gz | md5sum -c --quiet \
  && echo "data OK ($(zcat archives/MANIFEST_data.md5.gz | wc -l) files)"

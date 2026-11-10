#!/usr/bin/env bash
# Unpack the bundled data archives (data/archives/*.tar.gz) into data/, and
# optionally download the expert review package (entrypoint_review_v2.1.zip,
# 209 MB, GitHub release asset) which is not needed by any script.
#
#   scripts/fetch_data.sh            # extract data/fpea_out and data/link, verify md5
#   scripts/fetch_data.sh --zip      # also download the expert review package
#   FPEA_RELEASE_URL=<url-prefix> scripts/fetch_data.sh --zip   # override download location
#
# Everything runs inside data/ (set -e: the first failing tar/curl/checksum aborts the script).
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

# download_zip: fetch the expert review package into data/expert_pkg/ (curl, or urllib when curl
# is missing) unless it is already there, then check its sha256 against archives/SHA256SUMS
download_zip(){
  URL=${FPEA_RELEASE_URL:-https://github.com/FPEAJISA/FPEA/releases/download/v1.0}
  Z=expert_pkg/entrypoint_review_v2.1.zip
  if [ ! -f $Z ]; then
    echo "downloading $Z ..."
    if command -v curl >/dev/null; then
      curl -L -o $Z "$URL/entrypoint_review_v2.1.zip"
    else
      python3 -c "import urllib.request,sys; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])" \
        "$URL/entrypoint_review_v2.1.zip" $Z
    fi
  fi
  # SHA256SUMS holds one line (sha256, then the file name); sha256sum -c wants two spaces
  # before the path
  echo "$(cat archives/SHA256SUMS | awk '{print $1}')  $Z" | sha256sum -c
}

extract_archives
# the md5 check stays at top level: a failing md5sum must not abort the script (it is the
# left-hand side of the && list, so set -e ignores it) and the --zip step still runs
echo "verifying md5 of extracted files ..."
zcat archives/MANIFEST_data.md5.gz | md5sum -c --quiet \
  && echo "data OK ($(zcat archives/MANIFEST_data.md5.gz | wc -l) files)"

if [ "$1" = "--zip" ]; then
  download_zip
fi

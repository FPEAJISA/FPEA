"""Per-version aggregation of FPEA vs UAFX baseline results (5.17.11 ... 7.1.4-norand).

For each version reads the unit list ($FPEA_TMP/units.txt for 5.17.11, else <SP>/list_<V>.txt),
the FPEA JSON in <SP>/rf_<V>/ and the baseline text in <SP>/rw_<V>/.  Prints one line per
version and writes $FPEA_HOME/fpea_gt/final/version_results.json.
Invoked as `python3 aggregate_versions.py` from the scratchpad folder.
"""
import json
import os

# roots of the original measurement layout (set by env.sh: FPEA_HOME, FPEA_TMP, FPEA_WORK; on the
# measurement server they were the home directory, /tmp and the session scratchpad)
HOME_ROOT = os.environ.get('FPEA_HOME') or os.path.expanduser('~')
TMP_ROOT = os.environ.get('FPEA_TMP', '/tmp')

SP = os.environ.get('FPEA_WORK') or f'{TMP_ROOT}/scratchpad'
VERSIONS = ('5.17.11', '5.19.17', '6.9', '7.1.4', '7.1.4-norand')
OUT_JSON = f'{HOME_ROOT}/fpea_gt/final/version_results.json'


def unit_list(version):
    """Unit paths of one version (empty lines skipped)."""
    list_path = f'{TMP_ROOT}/units.txt' if version == '5.17.11' else f'{SP}/list_{version}.txt'
    return [line.strip() for line in open(list_path) if line.strip()]


def aggregate(version):
    """Totals of one version as the dict stored under its key in version_results.json."""
    files = unit_list(version)
    n_fpea = n_defined = 0
    miss_json = 0
    wl_set = set()
    fpea_set = set()
    wl_nonempty = 0
    wl_files = 0
    kinds = {}
    for bc in files:
        name = bc.replace('/', '_')
        fpea_path = f'{SP}/rf_{version}/{name}.json'
        if not os.path.exists(fpea_path):
            miss_json += 1
            continue
        fpea = json.load(open(fpea_path))
        n_fpea += len(fpea['entries'])
        n_defined += fpea['defined']
        for fn in fpea['entries']:
            fpea_set.add((bc, fn))
        wl_path = f'{SP}/rw_{version}/{name}.txt'
        if os.path.exists(wl_path):
            wl_files += 1
            wl_lines = [line.strip() for line in open(wl_path, errors='replace')
                        if line.strip()]
            if wl_lines:
                wl_nonempty += 1
            for line in wl_lines:
                parts = line.split(':')
                if len(parts) >= 2:
                    wl_set.add((bc, parts[1]))
                    kinds[parts[0]] = kinds.get(parts[0], 0) + 1
    inter = len(wl_set & fpea_set)
    n_wl = len(wl_set)
    return dict(units=len(files), fpea_json_missing=miss_json, FPEA=n_fpea, defined=n_defined,
                uafx_files=wl_files, uafx_nonempty=wl_nonempty, baseline=n_wl, inter=inter,
                wl_minus_fpea=n_wl - inter,
                miss_rate=round((n_fpea - inter) / n_fpea * 100, 2) if n_fpea else None,
                baseline_kinds=kinds)


def main():
    results = {}
    for version in VERSIONS:
        results[version] = aggregate(version)
        print(version, {k: v for k, v in results[version].items() if k != 'baseline_kinds'})
    with open(OUT_JSON, 'w') as out:
        json.dump(results, out, indent=1, ensure_ascii=False)


if __name__ == '__main__':
    main()

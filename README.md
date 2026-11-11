# FPEA reproducibility artifact

Artifact for the paper **"Function Pointer Escape Analysis for Entry Point Identification in Linux Kernel Drivers: Application to Cross-Entry Use-After-Free Detection"**.

It contains the FPEA tool, every script used for the measurements, the raw per-unit outputs of FPEA and of the UAFX baseline for five kernel trees, the expert reference set (two independent reviewers plus adjudication), the derived result files, the figures, and a verifier that recomputes ~340 numbers quoted in the paper (manuscript v2.3 / v3.1, November 2026) from the raw data and compares them.

The column names and rule labels of the expert data (translated from the Korean originals) are explained in [`docs/data_dictionary.md`](docs/data_dictionary.md).

## Quick check (minutes, no kernel build)

```
scripts/fetch_data.sh          # unpack data/archives/*.tar.gz into data/fpea_out and data/link, verify md5
./run_all.sh                   # derive + verify (light)
head -40 out/derive_report.md logs/verify_report.md
```

Requirements: Linux with bash and python3 (standard library only; tested on 3.10), 0.7 GB RAM, about 1 GB disk (49 MB checkout + 590 MB of extracted data), no root, no network beyond `git clone`. Takes about one minute.

Expected result on a fresh clone: every derived file `SAME` in `out/derive_report.md`, and `OK 334 / MISMATCH 0 / INFO 10` at the end of `logs/verify_report.md`. The `INFO` rows are not failures: reference values printed for the text (abstract reduction rates, recall bounds, a footnote, the two-file AT/F note, the pilot row count, the composition of a 50-item random sample) and two checks that are skipped when the measurement server's files are absent (the 5.17.11 source tree for the link-object/C-source count, and the first-run FPEA output `$FPEA_TMP/u_fpea` for the input-consistency check); on the measurement server both are real comparisons and the result is `OK 336 / INFO 8`. This was confirmed by copying the tracked files into an empty directory with an empty `$HOME` and running the two commands above; apart from those two optional inputs the scripts open nothing outside the checkout.

- `derive` rebuilds `version_results`, `strata_pop`, `typed_vs_opaque`, `randstruct_vs_norand_714`, `subsystem_ratio`, `fp_types`, `link_layer_q15`, the reference-set metrics (κ, precision, recall) and the bitcode-free part of the 2026-11-09 audit (`boot2_results`, `wl_ext`, `typed_mode_cmp`, see below) from `data/fpea_out`, `data/link` and `data/expert_pkg`, and compares them with the stored copies in `data/results`.
- `verify` recomputes the numbers quoted in the paper (each check is labelled with the section or table it belongs to) from the raw data. `verify-heavy` additionally re-reads bitcode and needs the kernel trees and LLVM (see below); on the measurement server it gives `OK 345 / MISMATCH 0 / INFO 8`.
- `audit` (needs the bitcode trees, about 10 minutes on 16 cores) re-runs the bitcode-dependent audit scripts (`popN`, `recon_pool2`, `defmap`, `wl_only`, `at_only`) into `out/` and compares them with `data/results`.

## Full reproduction (from the kernel builds, ~8 hours on 16 cores)

On a fresh Ubuntu 22.04 machine (16 cores, 32 GB RAM, 100 GB free disk recommended; 70 GB minimum; sudo and internet access for `setup.py`):

```
scripts/fetch_data.sh
python3 scripts/setup.py all   # checks the machine, apt packages, clang 14 (Ubuntu) + clang 16 (apt.llvm.org) + clang 14.0.6 release tarball, wllvm, kernel tarballs (sha256 pinned), original directory layout
./run_all.sh all               # 6 kernel builds + 1 debug build -> tools -> FPEA/UAFX on 5 trees -> analyses -> pilot -> derive -> figures -> verify-heavy
```

`setup.py` needs sudo for the apt step (or `--no-sudo` after installing the packages yourself). On a freshly booted machine the apt step can fail with `Could not get lock /var/lib/dpkg/lock-frontend … (unattended-upgr)`; wait until the automatic update has finished and run `setup.py all` again (every step skips what already exists). The full pipeline was run end to end on a separate 16-core VM, most recently on 2026-11-09 from a fresh Ubuntu 22.04 install using exactly the files in this repository as of that date (7 h 40 min): all build gates identical to the measurement server, derived results `SAME`, `verify-heavy OK 280 / MISMATCH 0 / INFO 11` (the verifier of that date; the 2026-11-10 verifier adds the audit checks and the fpea14 unit run, which were re-run and compared on the measurement server only). The `INFO` items are timing numbers and the deliberately non-deterministic checks listed under "What is not reproduced bit-for-bit" below.

Stages can be run one at a time: `./run_all.sh build-kernels | build-tools | run-fpea | analyses | sample | pilots | audit | derive | figures | verify | verify-heavy`.

**Where everything goes.** The reproduction needs no fixed path and no particular user name. Everything that `setup.py` and `run_all.sh` create (kernel build trees, bitcode, the clang 16 link and the clang 14.0.6 release, the kernel tarballs, the restored layout of the original scripts and their outputs) lives under `FPEA_HOME`, by default `work/` inside the checkout (ignored by git); the fixed-name files of the original session (`units.txt`, `u_fpea`, `fpea_out`, …) are under `FPEA_TMP`, by default `$FPEA_HOME/tmp`. To keep the ~70 GB on another disk, export `FPEA_HOME=/big/disk/fpea` before running `setup.py`; the layout step records the roots in `env.local.sh`, so later commands need no variable. Only the apt packages and wllvm (`pip --user`, `~/.local/bin`) are installed outside. The checkout path and `FPEA_HOME` must not contain spaces. On the measurement server the same layout lived directly under the home directory (`FPEA_HOME=$HOME`, `FPEA_TMP=/tmp`); the original scripts under `scripts/orig/` take these two roots from the environment (`HOME_ROOT`, `TMP_ROOT`) in place of the literal paths they had there, and are otherwise unchanged.

**Exit status.** `run_all.sh` stops at the first failing sub-step with a `FAILED: …` line and exit status 1 (the line names the step and its log). `derive_results.py` exits 1 when any derived file is not `SAME`, and `verify_numbers.py` exits 1 when any check is `MISMATCH` (`INFO` rows do not count), so `./run_all.sh` can be used as a pass/fail test. The two documented fallbacks (the stored copies used when the debug build tree or the KASAN "full" tree is absent, and the audit stage skipped in artifact mode without bitcode) are reported with a message and are not failures.

## Experiment environment

Everything in the paper was measured on one server; the full pipeline was then re-run from scratch on a separate VM to check that the recipe is self-contained. Both are described here so that readers can judge what hardware a re-run needs.

| | measurement server (paper numbers) | reproduction VM (2026-11-09 run) |
|---|---|---|
| OS / kernel | Ubuntu 22.04.2 LTS, Linux 6.8.0-136-generic | Ubuntu 22.04.5 LTS (fresh install) |
| CPU / RAM | Intel Xeon W-3275M 2.50 GHz, 16 cores, 78 GB | 16 vCPU, 31 GB |
| disk | 688 GB (about 65 GB used by this work) | 98 GB, 80 GB free before `setup.py`, 27 GB free at the end |
| clang 14 (typed IR kernel builds, UAFX baseline) | Ubuntu package `clang-14` 1:14.0.0-1ubuntu1.1 | same package |
| clang 16.0.6 (opaque-pointer IR, 7.1.4 builds, `fpea16`) | built from source (Release) | apt.llvm.org `llvm-toolchain-jammy-16` 16.0.6 |
| clang 14.0.6 (placeholder re-compile experiment, `llvm-dis`) | `clang+llvm-14.0.6-x86_64-linux-gnu-rhel-8.4` release tarball | same tarball (sha256 pinned in `setup.py`) |
| wllvm | 1.3.1 | 1.3.1 (`pip --user`) |
| python3 / matplotlib / numpy | 3.10.12 / 3.10.8 / 2.2.6 | 3.10.12 / 3.5.1 / 1.21 (Ubuntu packages) |
| kernel sources | kernel.org 5.17.11, 5.19.17, 6.9, 7.1.4 tarballs (sha256 pinned) | same |
| wall-clock of `run_all.sh all` | — | 7 h 40 min (see below) |

Disk needed for the full reproduction (measured on the VM): kernel tarballs 0.5 GB; six `drivers/`-only build trees 25 GB (5.17.11 clang 14 3.6, 5.17.11 clang 16 3.6, 5.19.17 3.8, 6.9 4.4, 7.1.4 4.9, 7.1.4-norand 4.9); the KASAN + `-g` debug build tree 22 GB; collected bitcode 5.5 GB; LLVM 16 packages 1.5 GB; LLVM 14.0.6 release 5.5 GB; apt packages 3 GB; this artifact with its outputs 2 GB. `setup.py` stops when the file system holding `FPEA_HOME` has less than 70 GB free and warns below 100 GB. The build trees must be kept after the build (the placeholder experiment reads their `.cmd` files and the header-offset parser reads their sources).

Time on the 16-core VM (2026-11-09 run): `setup.py all` 5 min; kernel builds 37 + 38 + 39 + 57 + 61 + 62 min (5 h 08 min including bitcode collection), debug build 40 min; link layer, tool build, FPEA/UAFX on five trees and the link-layer runs 13 min; analyses 1 h 38 min; pilot, derive, figures and `verify-heavy` about 1 min. Roughly double on 8 cores; the kernel builds need 8–16 GB RAM at `-j16`.

Network access needed only by `setup.py`: cdn.kernel.org (kernel tarballs), apt.llvm.org and Ubuntu mirrors (packages), github.com (LLVM 14.0.6 release), pypi.org (wllvm).

## Layout

| path | content |
|---|---|
| `run_all.sh`, `env.sh` | stage driver and all path/toolchain variables, every default derived from two roots: the checkout and `FPEA_HOME` (see above) |
| `tool/fpea.cpp`, `tool/build.sh` | the FPEA tool (LLVM 14 typed-IR and LLVM 16 opaque-pointer builds); `tool/uafx/` is the UAFX EntryPointIdentifier baseline |
| `scripts/` | `setup.py` (machine preparation), `build_kernel.sh` (wllvm kernel builds), `derive_results.py`, `verify_numbers.py`, `fetch_data.sh`; `scripts/orig/` are the original measurement scripts as `run_all.sh` runs them, reformatted for readability (functions, constants, docstrings; comments and console messages in English) with their logic, regexes, outputs and output order unchanged; `scripts/orig/audit_v23/` are the scripts of the 2026-11-09 audit (second-author review of manuscript v2.2 → v2.3: negative-sample design, address-taken-only tagging, whitelist-only decomposition, fpea14/fpea16 comparison) |
| `data/archives/` | `fpea_out.tar.gz` (per-unit FPEA / UAFX outputs for 5.17.11, 5.19.17, 6.9, 7.1.4, 7.1.4-norand and the clang 16 run, plus the fpea14 run on the 5.17.11 units `rf14_5.17.11`; 187,955 files) and `link.tar.gz` (link-layer outputs; 59,040 files), with an md5 manifest (`MANIFEST_data.md5.gz`); `review_package.tar.gz` (the expert review package, see below) |
| `data/expert_pkg/` | reviewer guideline `audit.txt` (v2.1), independent verdicts `rA.csv`, `rB.csv`, the 17 adjudicated conflicts (`adjudication_17*.csv`), ID maps (`unit_map_internal.json`, `adjudication_17_key_internal.json`); see `docs/data_dictionary.md` |
| `data/gt/`, `data/epi/`, `data/results/` | answer key and sample, UAFX whitelist / header offsets / filter validation, every result file quoted in the paper; the files of the 2026-11-09 audit are listed in `docs/data_dictionary.md` |
| `data/randstruct_7.1.4/` | the RANDSTRUCT seed of the 7.1.4 build (needed to reproduce the exact function counts) |
| `docs/` | data dictionary of the expert reference set (`data_dictionary.md`) |
| `figures/` | the 7 figures (pdf/png/svg) |
| `logs/`, `out/` | verification report and values of the measurement server (`verify_report.md`, `verify_values.json`), derived outputs and `derive_report.md` |
| `work/` (not in git) | created by `setup.py` and the full reproduction: `rerun/` (sources, build trees, original scripts), `linux_bc/`, `fpea_gt/final/`, `epi_regfn/`, `llvm/`, `llvm-14.0.7/`, `fpea_work/`, `tmp/` |

## What is not reproduced bit-for-bit

The expert verdicts (human input, stored), the 200-unit negative sample (depends on multiprocessing order; the actual sample is stored), the exact numbers of the contamination-filter validation (sample depends on filesystem walk order; re-run on the debug tree and reported as `INFO`), wall-clock timings, and the signed independence pledges of the reviewers, which are personal documents and are withheld from the public artifact.

## Expert review package

`data/archives/review_package.tar.gz` (5 MB) is the package handed to the two expert reviewers, `entrypoint_review_v2.1`: the reviewer guideline `audit.txt`, the blank verdict sheets `review_A.csv` / `review_B.csv` (the same 455 rows as `rA.csv` / `rB.csv` with the verdict columns empty), the blank independence pledge `pledge.txt`, and `build/` (the Kbuild `.cmd` files of the 353 sampled units and the `.config` of the 5.17.11 build). The package also contained 53,413 unmodified Linux 5.17.11 source files; they are not stored here because the same tarball is downloaded by `setup.py`, and `SOURCE_MANIFEST.txt` inside the archive lists every file with its md5 so the package can be rebuilt exactly. No script reads this archive.

## Language of the files

Everything in the artifact is in English. The expert review itself was conducted in Korean; the reviewer guideline (`audit.txt`), the column names and rule labels of the verdict and adjudication CSVs, and the reviewers' free-text remarks (also carried into `fp_types.json` / `tca_pilot_rows.json`) were translated by us with one fixed vocabulary, documented in `docs/data_dictionary.md`. The numeric content of every file is unchanged by the translation; `derive_results.py` and `verify_numbers.py` read the English names.

## License

MIT for our code, scripts, data and documents (`LICENSE`); third-party components keep their own licenses (`THIRD_PARTY.md`).

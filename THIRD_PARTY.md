# Third-party material

- `tool/uafx/main.cpp`, `tool/uafx/entry_point_handler_orig` — the EntryPointIdentifier LLVM pass of UAFX (https://github.com/uafx/uafx, built on SUTURE, which derives from the DR.CHECKER code base; source header "Created by machiry on 1/30/17"), kept verbatim in source and binary form as the baseline tool. License: BSD-2-Clause, Copyright (c) 2015, The Regents of the University of California; the full license text is reproduced in `tool/uafx/LICENSE` as the license requires for binary redistribution.
- `data/epi/uafx_kernel_sts.json` — the `kernel_sts` whitelist shipped with the public UAFX repository (same BSD-2-Clause license, `tool/uafx/LICENSE`).
- `data/archives/review_package.tar.gz` — the package handed to the two expert reviewers, without its copy of the Linux 5.17.11 sources (GPL-2.0, listed in `SOURCE_MANIFEST.txt` inside the archive); it keeps the Kbuild `.cmd` files and `.config` of our 5.17.11 build.
- Linux kernel sources 5.17.11 / 5.19.17 / 6.9 / 7.1.4 are downloaded from kernel.org by `scripts/setup.py` (GPL-2.0); they are not part of this repository.
- `scripts/setup.py` installs clang 14 (Ubuntu package), clang 16 (apt.llvm.org), the clang 14.0.6 release tarball and wllvm 1.3.1.

Everything else in this repository (the FPEA tool `tool/fpea.cpp`, scripts, data derived from our own measurements, documents) is covered by `LICENSE`.

# Numeric verification report (verify_numbers.py)

- checks 345: OK 345, MISMATCH 0, INFO 8

## All checks

| status | section | item | expected (paper) | recomputed | note |
|---|---|---|---|---|---|
| OK | 5.1/5.4 version table | 5.17.11 units | 15522 | 15522 |  |
| OK | 5.1/5.4 version table | 5.17.11 defined functions | 242823 | 242823 |  |
| OK | 5.1/5.4 version table | 5.17.11 FPEA | 129967 | 129967 |  |
| OK | 5.1/5.4 version table | 5.17.11 rf json missing | 0 | 0 |  |
| OK | 5.1/5.4 version table | 5.17.11 UAFX | 5899 | 5899 |  |
| OK | 5.1/5.4 version table | 5.17.11 FPEA∩UAFX | 4912 | 4912 |  |
| OK | 5.1/5.4 version table | 5.17.11 miss rate | 96.22 | 96.22 |  |
| OK | 5.1/5.4 version table | 5.19.17 units | 15913 | 15913 |  |
| OK | 5.1/5.4 version table | 5.19.17 defined functions | 249502 | 249502 |  |
| OK | 5.1/5.4 version table | 5.19.17 FPEA | 133213 | 133213 |  |
| OK | 5.1/5.4 version table | 5.19.17 rf json missing | 0 | 0 |  |
| OK | 5.1/5.4 version table | 5.19.17 UAFX | 6011 | 6011 |  |
| OK | 5.1/5.4 version table | 5.19.17 FPEA∩UAFX | 4983 | 4983 |  |
| OK | 5.1/5.4 version table | 5.19.17 miss rate | 96.26 | 96.26 |  |
| OK | 5.1/5.4 version table | 6.9 units | 17579 | 17579 |  |
| OK | 5.1/5.4 version table | 6.9 defined functions | 276117 | 276117 |  |
| OK | 5.1/5.4 version table | 6.9 FPEA | 146481 | 146481 |  |
| OK | 5.1/5.4 version table | 6.9 rf json missing | 0 | 0 |  |
| OK | 5.1/5.4 version table | 6.9 UAFX | 5527 | 5527 |  |
| OK | 5.1/5.4 version table | 6.9 FPEA∩UAFX | 4416 | 4416 |  |
| OK | 5.1/5.4 version table | 6.9 miss rate | 96.99 | 96.99 |  |
| OK | 5.1/5.4 version table | 7.1.4 units | 19649 | 19649 |  |
| OK | 5.1/5.4 version table | 7.1.4 defined functions | 301306 | 301306 |  |
| OK | 5.1/5.4 version table | 7.1.4 FPEA | 163919 | 163919 |  |
| OK | 5.1/5.4 version table | 7.1.4 rf json missing | 0 | 0 |  |
| OK | 5.1/5.4 version table | 7.1.4-norand units | 19649 | 19649 |  |
| OK | 5.1/5.4 version table | 7.1.4-norand defined functions | 301291 | 301291 |  |
| OK | 5.1/5.4 version table | 7.1.4-norand FPEA | 163919 | 163919 |  |
| OK | 5.1/5.4 version table | 7.1.4-norand rf json missing | 0 | 0 |  |
| OK | version_results.json | 5.17.11 FPEA stored=recomputed | 129967 | 129967 |  |
| OK | version_results.json | 5.19.17 FPEA stored=recomputed | 133213 | 133213 |  |
| OK | version_results.json | 6.9 FPEA stored=recomputed | 146481 | 146481 |  |
| OK | version_results.json | 7.1.4 FPEA stored=recomputed | 163919 | 163919 |  |
| OK | version_results.json | 7.1.4-norand FPEA stored=recomputed | 163919 | 163919 |  |
| OK | 5.1 input consistency | units whose rf_5.17.11 vs u_fpea sets differ | 0 | 0 |  |
| OK | Table 7 UAFX kinds | READ_HDR 5.17/5.19/6.9 | (984, 990, 609) | (984, 990, 609) |  |
| OK | Table 7 UAFX kinds | WRITE_HDR 5.17/5.19/6.9 | (891, 911, 560) | (891, 911, 560) |  |
| OK | Table 7 UAFX kinds | MY_IOCTL 5.17/5.19/6.9 | (489, 505, 345) | (489, 505, 345) |  |
| OK | Table 7 UAFX kinds | IOCTL_CAND 5.17/5.19/6.9 | (1388, 1415, 1469) | (1388, 1415, 1469) |  |
| OK | Table 7 UAFX kinds | INT_HANDLER_T 5.17/5.19/6.9 | (2506, 2552, 2736) | (2506, 2552, 2736) |  |
| OK | Table 7 UAFX kinds | NETDEVIOCTL 5.17/5.19/6.9 | (1, 1, 1) | (1, 1, 1) |  |
| OK | Table 7 UAFX kinds | READ_HDR 5.19→6.9 % | -38 | -38 |  |
| OK | Table 7 UAFX kinds | WRITE_HDR 5.19→6.9 % | -39 | -39 |  |
| OK | Table 7 UAFX kinds | MY_IOCTL 5.19→6.9 % | -32 | -32 |  |
| OK | Table 7 UAFX kinds | IOCTL_CAND 5.19→6.9 % | 4 | 4 |  |
| OK | Table 7 UAFX kinds | INT_HANDLER_T 5.19→6.9 % | 7 | 7 |  |
| INFO | Abstract (1) | READ/WRITE/IOCTL decrease rate (5.19→6.9) |  | (-38, -39, -32) | compare with the abstract sentence "down 38%/37%/29% … INT_HANDLER_T up 9%" (Table 7 has −38/−39/−32/+7) |
| OK | 5.3 WL∖FPEA | 5.17.11 WL∖FPEA | 987 | 987 |  |
| OK | Ch. 4 | 7.1.4 RANDSTRUCT vs norand FPEA identical | True | True |  |
| OK | 5.4(2) RANDSTRUCT control | common units | 19649 | 19649 |  |
| OK | 5.4(2) RANDSTRUCT control | units whose entry-point sets differ | 0 | 0 |  |
| OK | Table 2 stratum population | C1 | 90831 | 90831 |  |
| OK | strata_pop.json | C1 | 90831 | 90831 |  |
| OK | Table 2 stratum population | C4only | 16329 | 16329 |  |
| OK | strata_pop.json | C4only | 16329 | 16329 |  |
| OK | Table 2 stratum population | C3 | 8874 | 8874 |  |
| OK | strata_pop.json | C3 | 8874 | 8874 |  |
| OK | Table 2 stratum population | C5 | 1331 | 1331 |  |
| OK | strata_pop.json | C5 | 1331 | 1331 |  |
| OK | Table 2 stratum population | C2 only | 12602 | 12602 |  |
| OK | Table 2 stratum population | nF | 129967 | 129967 |  |
| OK | Table 2 stratum population | defined functions | 242823 | 242823 |  |
| OK | Table 2 share % | C1 | 69.9 | 69.9 |  |
| OK | Table 2 share % | C2 | 9.7 | 9.7 |  |
| OK | Table 2 share % | C3 | 6.8 | 6.8 |  |
| OK | Table 2 share % | C4only | 12.6 | 12.6 |  |
| OK | Table 2 share % | C5 | 1.0 | 1.0 |  |
| OK | Table 2 weight W | C1 | 0.6989 | 0.6989 |  |
| OK | Table 2 weight W | C4only | 0.1256 | 0.1256 |  |
| OK | Table 2 weight W | C3 | 0.0683 | 0.0683 |  |
| OK | Table 2 weight W | C5 | 0.0102 | 0.0102 |  |
| OK | Table 2 weight W | C2 | 0.097 | 0.097 |  |
| OK | Table 2 auxiliary | C1∩C4 | 161 | 161 |  |
| OK | Table 2 auxiliary | C3 only | 8798 | 8798 |  |
| OK | 5.10 | FPEA/defined functions % | 53.5 | 53.5 |  |
| OK | Ch. 1 | C2-only 12,602 have 0 in UAFX | 0 | 0 |  |
| OK | Table 3 | reference set n | 455 | 455 |  |
| OK | Table 3 | rA/rB ids identical | True | True |  |
| OK | Table 3 | positives | 255 | 255 |  |
| OK | Table 3 | negatives | 200 | 200 |  |
| OK | Table 3 | positive stratum composition | {'C1': 80, 'C4only': 70, 'C3': 60, 'C5': 45} | {'C3': 60, 'C1': 80, 'C4only': 70, 'C5': 45} |  |
| OK | Table 3 | answer key vs current FPEA output mismatches (signals; same-named units pass if either matches) | 0 | 0 |  |
| OK | Table 3 | answer-key (function, module) pairs spanning two units | ['G128'] | ['G128'] | if_usb (libertas/libertas_tf) same-named units; the verdict unit is fixed by unit_map_internal.json |
| OK | Table 3 | final label distribution | {'1': 218, '0': 222, '?': 15} | {'0': 222, '1': 218, '?': 15} |  |
| OK | Table 3 | 1↔0 conflicts | 17 | 17 |  |
| OK | Table 3 | adjudication outcome 1/0 | {'1': 6, '0': 11} | {'1': 6, '0': 11} |  |
| OK | Table 3 | adjudication file ids = conflict ids | True | True |  |
| OK | 5.2 | changes after discussion (revised column) | 5 | 5 |  |
| OK | 5.2 | verdicts changed vs first reply (4) + reason-only replacement (1) = 5 | (4, 5) | (4, 5) | G034·G317→1, G315·G046→0, G136 reason replaced |
| OK | 5.2 | TP before correction (first reply) | 218 | 218 |  |
| OK | Table 3 | agreement rate | 0.963 | 0.963 |  |
| OK | Table 3 | κ | 0.93 | 0.93 |  |
| OK | Table 4 | TP | 218 | 218 |  |
| OK | Table 4 | FP | 37 | 37 |  |
| OK | Table 4 | C1 TP/FP | (74, 6) | (74, 6) |  |
| OK | Table 4 | C1 precision | 0.925 | 0.925 |  |
| OK | Table 4 | C1 CI | (0.846, 0.965) | (0.846, 0.965) |  |
| OK | Table 4 | C4only TP/FP | (63, 7) | (63, 7) |  |
| OK | Table 4 | C4only precision | 0.9 | 0.9 |  |
| OK | Table 4 | C4only CI | (0.808, 0.951) | (0.808, 0.951) |  |
| OK | Table 4 | C3 TP/FP | (50, 10) | (50, 10) |  |
| OK | Table 4 | C3 precision | 0.833 | 0.833 |  |
| OK | Table 4 | C3 CI | (0.72, 0.907) | (0.72, 0.907) |  |
| OK | Table 4 | C5 TP/FP | (31, 14) | (31, 14) |  |
| OK | Table 4 | C5 precision | 0.689 | 0.689 |  |
| OK | Table 4 | C5 CI | (0.543, 0.805) | (0.543, 0.805) |  |
| OK | Table 4 | simple precision | 0.855 | 0.855 |  |
| OK | Table 4 | simple precision CI | (0.806, 0.893) | (0.806, 0.893) |  |
| OK | Table 4 | weighted precision excl. C2 (measured, headline) | 0.912 | 0.912 | exact value 0.91191; four strata, W renormalised by 0.9030 |
| OK | Table 4 | weighted SE excl. C2 (n-1) | 0.0238 | 0.0238 |  |
| OK | Table 4 | weighted CI excl. C2 | (0.865, 0.959) | (0.865, 0.959) |  |
| OK | Table 4 | weighted precision incl. C2 (W_true) | 0.92 | 0.92 | exact value 0.92045; with 3-digit rounded weights (0.699/0.128/0.068/0.010/0.098) it is 0.9206→0.921. The text uses 0.920 (W_true) for population estimates |
| OK | Table 4 | weighted SE incl. C2 (n-1) | 0.0215 | 0.0215 |  |
| OK | Table 4 | weighted CI incl. C2 | (0.878, 0.963) | (0.878, 0.963) |  |
| OK | 5.2 | over-approximation rate 1 - precision incl. C2 (%) | 8.0 | 8.0 |  |
| OK | 5.2 | negatives confirmed FN | 0 | 0 |  |
| OK | 5.2 | negatives ? | 15 | 15 |  |
| OK | 5.1 | defined functions after the 3.4 filter | 236515 | 236515 |  |
| OK | 5.1 | defined functions before the filter (llvm-dis = fpea json) | (242823, 242823) | (242823, 242823) |  |
| OK | Appendix D / S11 | filter removes (header inline copies) | 6308 | 6308 |  |
| OK | 5.2 | negative population |N| (post-filter) | 106548 | 106548 |  |
| OK | 5.2 | |N| = popN N_clean | 106548 | 106548 |  |
| OK | 5.10 | pre-filter negative population (sensitivity) | 112856 | 112856 |  |
| OK | 5.2 | TP_pop | 119629 | 119629 |  |
| OK | 5.2 | FN_pop (ratio estimator) | 7991 | 7991 |  |
| OK | 5.2 | recall (ratio estimator, primary) | 0.937 | 0.937 |  |
| OK | 5.2 | recall Wilson CI (SRS assumption) | (0.903, 0.961) | (0.903, 0.961) |  |
| OK | 5.10 | pre-filter FN / recall (sensitivity) | (8464, 0.934) | (8464, 0.934) |  |
| OK | 5.10 | pre-filter FN inflation % | 6 | 6 |  |
| INFO | 5.2 alternative | recall (direct sum of sample counts) |  | 0.936 |  |
| INFO | 5.2 alternative | rule-of-three recall lower bound |  | 0.987 |  |
| INFO | 5.2 alternative | ?=0 recall CI |  | (0.983, 1.0) |  |
| OK | 5.2 ?15 | all 15 have A=B=? and rule other-file | True | True |  |
| OK | 5.2 ?15 | no ? in positive sample | 0 | 0 |  |
| OK | Table 5 | FP types | {'internal-dispatch': 27, 'sync-callback': 7, 'internal-dispatch/sync-callback': 3} | {'internal-dispatch': 27, 'internal-dispatch/sync-callback': 3, 'sync-callback': 7} |  |
| OK | Table 5 | internal-dispatch per stratum | {'C1': 6, 'C4only': 6, 'C3': 2, 'C5': 13} | {'C1': 6, 'C5': 13, 'C4only': 6, 'C3': 2} |  |
| OK | Table 5 | sync-callback per stratum | {'C3': 7} | {'C3': 7} |  |
| OK | Table 5 | mixed per stratum | {'C4only': 1, 'C3': 1, 'C5': 1} | {'C4only': 1, 'C3': 1, 'C5': 1} |  |
| OK | Table 5 | FP per-stratum total | {'C1': 6, 'C4only': 7, 'C3': 10, 'C5': 14} | {'C1': 6, 'C5': 14, 'C4only': 7, 'C3': 10} |  |
| OK | Table 5/D3 | G162 final rule (adjudicated) | internal-dispatch | internal-dispatch |  |
| OK | Table 5/D3 | G162 B rule | sync-callback | sync-callback |  |
| OK | fp_types.json | fp_ids = recomputed | ['G011', 'G012', 'G042', 'G043', 'G046', 'G061', 'G064', 'G086', 'G139', 'G159', 'G162', 'G182', 'G183', 'G195', 'G213', 'G229', 'G247', 'G269', 'G274', 'G289', 'G305', 'G308', 'G313', 'G315', 'G318', 'G321', 'G323', 'G340', 'G389', 'G399', 'G400', 'G401', 'G430', 'G441', 'G446', 'G447', 'G455'] | ['G011', 'G012', 'G042', 'G043', 'G046', 'G061', 'G064', 'G086', 'G139', 'G159', 'G162', 'G182', 'G183', 'G195', 'G213', 'G229', 'G247', 'G269', 'G274', 'G289', 'G305', 'G308', 'G313', 'G315', 'G318', 'G321', 'G323', 'G340', 'G389', 'G399', 'G400', 'G401', 'G430', 'G441', 'G446', 'G447', 'G455'] |  |
| OK | Table 3 | A rule distribution | {'internal-helper': 153, 'exported-service': 35, 'deferred': 43, 'op-table': 142, 'internal-dispatch': 17, 'probe-remove': 15, 'teardown': 6, 'irq': 18, 'other-file': 15, 'sync-callback': 10, 'comparison': 1} | {'internal-helper': 153, 'exported-service': 35, 'deferred': 43, 'op-table': 142, 'internal-dispatch': 17, 'probe-remove': 15, 'teardown': 6, 'irq': 18, 'other-file': 15, 'sync-callback': 10, 'comparison': 1} |  |
| OK | Table 3 | B rule distribution | {'internal-helper': 150, 'exported-service': 35, 'deferred': 47, 'op-table': 129, 'internal-dispatch': 30, 'probe-remove': 17, 'teardown': 8, 'irq': 16, 'other-file': 15, 'sync-callback': 8} | {'internal-helper': 150, 'exported-service': 35, 'deferred': 47, 'op-table': 129, 'internal-dispatch': 30, 'probe-remove': 17, 'teardown': 8, 'irq': 16, 'other-file': 15, 'sync-callback': 8} |  |
| OK | Table 3 | TP rules | {'op-table': 125, 'deferred': 40, 'irq': 15, 'probe-remove': 13, 'teardown': 7, 'mixed': 18} | {'deferred': 40, 'op-table': 125, 'probe-remove': 13, 'teardown': 7, 'irq': 15, 'mixed': 18} |  |
| OK | Appendix D / S11 | duplicate-name drop never triggered (quota 255 = final 255) | (255, 255) | (255, 255) |  |
| OK | Appendix D / S11 | positives with a same-name entry point in another unit | 11 | 11 |  |
| OK | Appendix D sample reproduction | positives 255 (seed 517) reproduced | True | True | unit order = stored original list, function order = stored original output; the 200 negatives depend on Pool order (imap_unordered) and cannot be reproduced from the seed alone → kept in gt_sample_unit.json |
| OK | Appendix D sample reproduction | gt_sample_unit.json negatives = answer-key negatives | True | True |  |
| OK | 5.9(a) | link_layer_q15 id = ? 15 | ['G085', 'G105', 'G120', 'G141', 'G154', 'G194', 'G219', 'G260', 'G266', 'G295', 'G361', 'G372', 'G386', 'G428', 'G439'] | ['G085', 'G105', 'G120', 'G141', 'G154', 'G194', 'G219', 'G260', 'G266', 'G295', 'G361', 'G372', 'G386', 'G428', 'G439'] |  |
| OK | 5.9(a) | identified 15/15 in the link layer, C1 13 / C4 2 | {'C1': 13, 'C4': 2} | {'C1': 13, 'C4': 2} |  |
| OK | Appendix H | dcn10_init.c registration count | 8 | 8 |  |
| OK | Table 12 | units 14/16 | (15522, 15452) | (15522, 15452) |  |
| OK | Table 12 | common units | 15451 | 15451 |  |
| OK | Table 12 | FPEA common typed/opaque | (128571, 128541) | (128571, 128541) |  |
| OK | Table 12 | differing units / symmetric difference | (8, 30) | (8, 30) |  |
| OK | Table 12 | functions only in opaque | 0 | 0 |  |
| OK | Table 12 | FPEA total opaque | 128544 | 128544 |  |
| OK | Table 12 | opaque simple hit rate | (43.81, 3879, 8855) | (43.81, 3879, 8855) |  |
| OK | Table 11 simple hit rate | 5.17.11 | (8807, 3862, 43.85) | (8807, 3862, 43.85) |  |
| OK | Table 11 semantic file agreement | 5.17.11 | (8807, 3862) | (8807, 3862) |  |
| OK | Table 11 simple hit rate formula | 5.17.11 | 43.85 | 43.85 |  |
| OK | Table 11 simple hit rate | 5.19.17 | (8964, 3944, 44.0) | (8964, 3944, 44.0) |  |
| OK | Table 11 semantic file agreement | 5.19.17 | (8964, 3944) | (8964, 3944) |  |
| OK | Table 11 simple hit rate formula | 5.19.17 | 44.0 | 44.0 |  |
| OK | Table 11 simple hit rate | 6.9 | (5914, 2455, 41.51) | (5914, 2455, 41.51) |  |
| OK | Table 11 semantic file agreement | 6.9 | (5914, 2455) | (5914, 2455) |  |
| OK | Table 11 simple hit rate formula | 6.9 | 41.51 | 41.51 |  |
| OK | Table 11 simple hit rate | 7.1.4-norand | (11136, 5919, 53.15) | (11136, 5919, 53.15) |  |
| OK | Table 11 semantic file agreement | 7.1.4-norand | (11136, 5919) | (11136, 5919) |  |
| OK | Table 11 simple hit rate formula | 7.1.4-norand | 53.15 | 53.15 |  |
| OK | Table 11 simple hit rate | 7.1.4 | (11136, 6127, 55.02) | (11136, 6127, 55.02) |  |
| OK | Table 11 semantic file agreement | 7.1.4 | (11136, 6127) | (11136, 6127) |  |
| OK | Table 11 simple hit rate formula | 7.1.4 | 55.02 | 55.02 |  |
| OK | Table 11 semantic hit rate | 5.17.11 | (7060, 7060, 3290, 46.6, 0, 0) | (7060, 7060, 3290, 46.6, 0, 0) |  |
| OK | Table 11 semantic hit rate formula | 5.17.11 | 46.6 | 46.6 |  |
| OK | Table 11 semantic hit rate | 5.19.17 | (7183, 7147, 3341, 46.51, 23, 4) | (7183, 7147, 3341, 46.51, 23, 4) |  |
| OK | Table 11 semantic hit rate formula | 5.19.17 | 46.51 | 46.51 |  |
| OK | Table 11 semantic hit rate | 6.9 | (4055, 2922, 1724, 42.52, 93, 100) | (4055, 2922, 1724, 42.52, 93, 100) |  |
| OK | Table 11 semantic hit rate formula | 6.9 | 42.52 | 42.52 |  |
| OK | Table 11 semantic hit rate | 7.1.4-norand | (9185, 3163, 532, 5.79, 4732, 3748) | (9185, 3163, 532, 5.79, 4732, 3748) |  |
| OK | Table 11 semantic hit rate formula | 7.1.4-norand | 5.79 | 5.79 |  |
| OK | Table 11 | 6.9 index-shifted slots | 1133 | 1133 |  |
| OK | Table 9 named/literal | 5.17.11 file_operations/LITERAL | (2102, 12) | (2102, 12) |  |
| OK | Table 9 named/literal | 5.17.11 platform/pci/device_attribute/net_device_ops | (2852, 710, 4699, 386) | (2852, 710, 4699, 386) |  |
| OK | Table 9 named/literal | 5.19.17 file_operations/LITERAL | (2140, 12) | (2140, 12) |  |
| OK | Table 9 named/literal | 5.19.17 platform/pci/device_attribute/net_device_ops | (2973, 713, 4781, 391) | (2973, 713, 4781, 391) |  |
| OK | Table 9 named/literal | 6.9 file_operations/LITERAL | (1102, 1347) | (1102, 1347) |  |
| OK | Table 9 named/literal | 6.9 platform/pci/device_attribute/net_device_ops | (3464, 717, 5176, 381) | (3464, 717, 5176, 381) |  |
| OK | Table 9 | 6.9 literal share % | 55 | 55 |  |
| OK | Table 9 | 5.17.11 LLVM16 named | 2114 | 2114 |  |
| OK | Table 9 | 7.1.4 norand named / strict literal pattern | (2800, 21) | (2800, 21) |  |
| OK | Table 9 | 7.1.4 RANDSTRUCT named / strict literal pattern | (2800, 21) | (2800, 21) |  |
| OK | Table 9 placeholder units | 5.17.11 | (28, 15522) | (28, 15522) |  |
| OK | Table 9 placeholder units | 5.19.17 | (28, 15913) | (28, 15913) |  |
| OK | Table 9 placeholder units | 6.9 | (11451, 17579) | (11451, 17579) |  |
| OK | Table 8 kind_drift | READ_HDR | (369, 10, 356, 3, 0, 0) | (369, 10, 356, 3, 0, 0) |  |
| OK | Table 8 kind_drift sum | READ_HDR | 369 | 369 |  |
| OK | Table 8 kind_drift | WRITE_HDR | (356, 22, 331, 3, 0, 0) | (356, 22, 331, 3, 0, 0) |  |
| OK | Table 8 kind_drift sum | WRITE_HDR | 356 | 356 |  |
| OK | Table 8 kind_drift | MY_IOCTL | (150, 8, 138, 3, 0, 1) | (150, 8, 138, 3, 0, 1) |  |
| OK | Table 8 kind_drift sum | MY_IOCTL | 150 | 150 |  |
| OK | Table 8 kind_drift | INT_HANDLER_T | (38, 29, 5, 0, 0, 4) | (38, 29, 5, 0, 0, 4) |  |
| OK | Table 8 kind_drift sum | INT_HANDLER_T | 38 | 38 |  |
| OK | Table 10/①③ | struct count / handler name count | (20, 17) | (20, 17) |  |
| OK | Table 10/①③ | tracked 59 / moved 23 | (59, 23) | (59, 23) |  |
| OK | Table 10/①③ | moved share % | 39 | 39 |  |
| OK | 5.4(3) footnote | moved within the three versions 5.17·5.19·6.9 / direct 5.17 vs 7.1 comparison | (19, 15) | (19, 15) |  |
| INFO | 5.4(3) footnote | 5.17 vs 6.9 direct comparison (reference) |  | 17 | the 19 in the footnote counts handlers that differ at least once across the three versions |
| OK | Table 10 index | file_operations.llseek | (1, 1, 1, 2) | (1, 1, 1, 2) |  |
| OK | Table 10 index | file_operations.read | (2, 2, 2, 3) | (2, 2, 2, 3) |  |
| OK | Table 10 index | file_operations.write | (3, 3, 3, 4) | (3, 3, 3, 4) |  |
| OK | Table 10 index | file_operations.unlocked_ioctl | (10, 10, 9, 10) | (10, 10, 9, 10) |  |
| OK | Table 10 index | file_operations.compat_ioctl | (11, 11, 10, 11) | (11, 11, 10, 11) |  |
| OK | Table 10 index | file_operations.mmap | (12, 12, 11, 12) | (12, 12, 11, 12) |  |
| OK | Table 10 index | file_operations.open | (14, 14, 13, 13) | (14, 14, 13, 13) |  |
| OK | Table 10 index | file_operations.release | (16, 16, 15, 15) | (16, 16, 15, 15) |  |
| OK | Table 10 index | pci_driver.probe | (3, 3, 2, 2) | (3, 3, 2, 2) |  |
| OK | Table 10 index | pci_driver.remove | (4, 4, 3, 3) | (4, 4, 3, 3) |  |
| OK | Table 10 index | pci_driver.suspend | (5, 5, 4, 4) | (5, 5, 4, 4) |  |
| OK | Table 10 index | pci_driver.resume | (6, 6, 5, 5) | (6, 6, 5, 5) |  |
| OK | Table 10 index | net_device_ops.ndo_validate_addr | (10, 10, 10, 11) | (10, 10, 10, 11) |  |
| OK | Table 10 index | block_device_operations.rw_page | (3, 4, None, None) | (3, 4, None, None) |  |
| OK | Table 10 index | platform_driver.probe | (0, 0, 0, 0) | (0, 0, 0, 0) |  |
| OK | Table 10 index | platform_driver.remove | (1, 1, 1, 1) | (1, 1, 1, 1) |  |
| OK | Table 10 index | device_driver.probe | (8, 8, 8, 8) | (8, 8, 8, 8) |  |
| OK | Table 10 index | net_device_ops.ndo_open | (2, 2, 2, 2) | (2, 2, 2, 2) |  |
| OK | Table 10 index | 6.9 rule 10 = compat_ioctl | compat_ioctl | compat_ioctl |  |
| OK | Table 10 index | 7.1 rule 2/3 = llseek/read | ('llseek', 'read') | ('llseek', 'read') |  |
| OK | Table 10 index | 7.1 ndo rule 10 = ndo_set_mac_address | ndo_set_mac_address | ndo_set_mac_address |  |
| OK | Ch. 1/Table 10 | bitcode struct field counts: 25 of 33 changed | (33, 25) | (33, 25) | epi_regfn/struct_drift_full.json (preliminary measurement on the LLVM16 full tree) |
| OK | Ch. 1/Table 1 | kernel_sts entries/structs | (88, 51) | (88, 51) |  |
| OK | 5.9(b) | entry points/defined/miss rate | (139678, 249121, 96.24) | (139678, 249121, 96.24) |  |
| OK | 5.9(c) | framework-optable/lifecycle/user-triggered/interrupt | (58130, 12717, 16451, 2439) | (58130, 12717, 16451, 2439) |  |
| OK | Ch. 1 | configfs_attribute / clk_ops (link-layer behavior top) | (1075, 1031) | (1075, 1031) |  |
| OK | 3.7 / Table S2 | address-taken 143,632 (analyze3.json; the pair quoted in the text) | 143632 | 143632 |  |
| OK | 3.7 / Table S2 | AT only 16,556 (analyze3.json) | 16556 | 16556 |  |
| OK | 3.7 | FPEA = AT - AT-only + C2-only (139,678) | 139678 | 139678 |  |
| INFO | 3.7 caution | AT / F of atfinal.json (different file set) |  | (144294, 139236) | atfinal.json analyses a different set (substitute units for FAIL modules; run time): AT 144,294. The text cites analyze3.json (143,632 / 139,678 / 16,556) only |
| OK | 5.9 | .mod 6,865 = linked 6,853 + failed 12; builtin 1,925 | (6853, 12, 1925) | (6853, 12, 1925) | the "6,865 modules" in skeleton 5.9 is the .mod count; bitcode is 6,853 |
| OK | 5.9 | link-layer FPEA output count (fpea_out, modules+builtin) | 8778 | 8778 | the earlier 8,790 is .mod 6,865+1,925; actual analysed files 6,853+1,925=8,778 (+substitute units for failed modules) |
| OK | 5.3 caution | analyze3 wl_miss (link-layer WmF 424) IOCTL_CAND|external / INT_HANDLER_T|external | (314, 58) | (314, 58) | text 5.3 uses the unit-layer 987 together with this link-layer breakdown, mixing layers → recompute the unit-layer breakdown with --heavy |
| OK | Ch. 4 | allmodconfig modules (llvm14) | 8519 | 8519 |  |
| OK | Ch. 4 | drivers .o / wllvm .bc | (16849, 15521) | (16849, 15521) |  |
| OK | Ch. 4 | units.txt = drivers 15,520 + scripts 1 + tools 1 | (15520, 2) | (15520, 2) | differs by 1 from the drivers .bc 15,521 in all.log: the unit list is 15,520 drivers + 2 non-drivers |
| OK | Ch. 4 | .o without bc | 1328 | 1328 |  |
| OK | Ch. 4 | composite link objects / no C source | (1275, 53) | (1275, 53) | Makefile <name>-y/-objs rules re-parsed |
| OK | Ch. 4 | objects with a matching .c but no bc | 0 | 0 |  |
| OK | Table 15 | sequential/parallel s | (179.9, 16.4) | (179.9, 16.4) |  |
| OK | Table 15 | ms per unit | 11.6 | 11.6 |  |
| OK | Table 15 | UAFX 5.17.11 14-way parallel s | 37 | 37 |  |
| OK | Table 15 | speed-up vs UAFX | 2.3 | 2.3 |  |
| OK | Ch. 1 entry surface | syscall/ioctl uapi/all/fops/ops/init/exit/irq | (362, 1914, 2229, 1734, 3831, 2053, 2462, 3488) | (362, 1914, 2229, 1734, 3831, 2053, 2462, 3488) |  |
| OK | 3.4 filter | 400 modules 8,429 / 96.0% / over 332 / missed 4 | (400, 8429, 96.0, 332, 4) | (400, 8429, 96.0, 332, 4) | 400-module sample from the debug (-g) build tree (os.walk order = filesystem order, so the sample differs per machine); rerun re-runs it on the build_kernel.sh dbg tree and records it as INFO alongside; if the tree is absent run_all.sh keeps the stored copy |
| OK | 3.3/5.10 | C3 synchronous-callback over-estimate 1,092 | 1092 | 1092 | link-layer measurement (F 138,376 before the EXPORT fix) |
| OK | Table 13 | FPEA total n/free/v1/v2/any1/any2 | (129967, 12942, 41822, 29526, 48258, 38176) | (129967, 12942, 41822, 29526, 48258, 38176) |  |
| OK | Table 13 | missed n/free/v1/v2/any1/any2 | (125055, 12388, 40262, 28435, 46447, 36790) | (125055, 12388, 40262, 28435, 46447, 36790) |  |
| OK | Table 13 | share % | (29.4, 37.1, 29.4, 37.1, 15.7, 19.9) | (29.4, 37.1, 29.4, 37.1, 15.7, 19.9) |  |
| OK | Table 13 | M_n = FPEA − intersection | 125055 | 125055 |  |
| OK | Table 16 subsystem | watchdog | 90.4 | 90.4 |  |
| OK | subsystem_ratio.json | watchdog | (1199, 1084) | (1199, 1084) |  |
| OK | Table 16 subsystem | hwmon | 88.0 | 88.0 |  |
| OK | subsystem_ratio.json | hwmon | (3445, 3031) | (3445, 3031) |  |
| OK | Table 16 subsystem | rtc | 87.9 | 87.9 |  |
| OK | subsystem_ratio.json | rtc | (1801, 1583) | (1801, 1583) |  |
| OK | Table 16 subsystem | gpio | 85.3 | 85.3 |  |
| OK | subsystem_ratio.json | gpio | (1910, 1630) | (1910, 1630) |  |
| OK | Table 16 subsystem | iio | 80.6 | 80.6 |  |
| OK | subsystem_ratio.json | iio | (4843, 3902) | (4843, 3902) |  |
| OK | Table 16 subsystem | input | 77.0 | 77.0 |  |
| OK | subsystem_ratio.json | input | (3720, 2866) | (3720, 2866) |  |
| OK | Table 16 subsystem | hid | 73.5 | 73.5 |  |
| OK | subsystem_ratio.json | hid | (1956, 1438) | (1956, 1438) |  |
| OK | Table 16 subsystem | tty | 71.6 | 71.6 |  |
| OK | subsystem_ratio.json | tty | (2977, 2133) | (2977, 2133) |  |
| OK | Table 16 subsystem | media | 63.6 | 63.6 |  |
| OK | subsystem_ratio.json | media | (19955, 12686) | (19955, 12686) |  |
| OK | Table 16 subsystem | usb | 54.5 | 54.5 |  |
| OK | subsystem_ratio.json | usb | (9260, 5048) | (9260, 5048) |  |
| OK | Table 16 subsystem | scsi | 45.0 | 45.0 |  |
| OK | subsystem_ratio.json | scsi | (12935, 5823) | (12935, 5823) |  |
| OK | Table 16 subsystem | gpu | 45.0 | 45.0 |  |
| OK | subsystem_ratio.json | gpu | (31383, 14123) | (31383, 14123) |  |
| OK | Table 16 subsystem | net | 44.2 | 44.2 |  |
| OK | subsystem_ratio.json | net | (58112, 25666) | (58112, 25666) |  |
| OK | Table 16 subsystem | md | 42.5 | 42.5 |  |
| OK | subsystem_ratio.json | md | (2884, 1226) | (2884, 1226) |  |
| OK | Table 16 subsystem | staging | 34.7 | 34.7 |  |
| OK | subsystem_ratio.json | staging | (9008, 3126) | (9008, 3126) |  |
| OK | Table 16 subsystem | acpi | 34.2 | 34.2 |  |
| OK | subsystem_ratio.json | acpi | (2184, 748) | (2184, 748) |  |
| OK | Table 16 subsystem | infiniband | 28.6 | 28.6 |  |
| OK | subsystem_ratio.json | infiniband | (7854, 2244) | (7854, 2244) |  |
| INFO | TCA pilot | rows |  | 455 |  |
| OK | TCA pilot | callers 0 among TP 218 / callers 0 among FP 37 / callers 0 among negatives labelled 0 (185) / callers 0 among ? 15 | (210, 36, 105, 15) | (210, 36, 105, 15) | final/tca_pilot.log; direct caller count r |
| OK | 5.4 placeholder | placeholder_trigger.log exists | True | True |  |
| OK | 5.2 / S11 | stage-1 units / pool / zero units / max unit | (500, 3071, 122, 100) | (500, 3071, 122, 100) |  |
| OK | 5.2 / S11 | pool = sum of per-unit sizes | 3071 | 3071 |  |
| OK | 5.2 / S11 | all 200 negatives are members of the pool | 200 | 200 |  |
| OK | S11 | median pool size per unit | 2 | 2 |  |
| OK | 5.2 | conditional inclusion probability 200/|pool(S)| | 0.065 | 0.065 |  |
| OK | 5.2 | unconditional inclusion probability (approx.) | 0.0021 | 0.0021 | 500/15,522 x 200/3,071 (the text says approximately 0.0021) |
| OK | 5.2 | pool density of the selected units vs population (per unit) | (6.1, 6.9) | (6.1, 6.9) |  |
| OK | 5.2 | expansion estimator FN_S = |pool|/200 * 15 | 230 | 230 |  |
| OK | 5.2 | expansion estimator FN_HT = 15,522/500 * FN_S | 7150 | 7150 |  |
| OK | 5.2 | recall (expansion estimator, sensitivity) | 0.944 | 0.944 |  |
| OK | 5.2 | recall (ratio estimator) from boot2 | 0.937 | 0.937 |  |
| OK | 5.2 / S5 | unit bootstrap 95% (ratio estimator) | (0.873, 0.984) | (0.873, 0.984) |  |
| OK | S5 | unit bootstrap 95% (TP fixed, negatives only) | (0.874, 0.985) | (0.874, 0.985) |  |
| OK | 5.2 / S5 | unit bootstrap 95% (expansion estimator) | (0.874, 0.987) | (0.874, 0.987) |  |
| OK | 5.2 / S5 | design effect d | 4.34 | 4.34 |  |
| OK | 5.2 | dcn10_hw_sequencer.c pool 59 / expected sample 3.8 / observed 8 | (59, 3.8, 8) | (59, 3.8, 8) |  |
| OK | 5.2 | FN 15 = 8 in one unit + 7 in 7 other units | (8, 7) | (8, 7) |  |
| OK | S11 | TP_hat / precision excl. / incl. C2 (boot2) | (119629, 0.912, 0.92) | (119629, 0.912, 0.92) |  |
| OK | Appendix H / S15 | FN estimate range from Wilson 4.6-12.0% of |N| | (4900, 12800) | (4900.0, 12800.0) | the text rounds to about 4,900 - 12,800 |
| OK | Table S2 | AT-only pairs | 16556 | 16556 |  |
| OK | Table S2 | EXPORT by-product globals only | 16266 | 16266 |  |
| OK | Table S2 | phi/select/ret result used immediately | 205 | 205 |  |
| OK | Table S2 | icmp comparison only (4 + 1) | 5 | 5 |  |
| OK | Table S2 | argument of a call through a function pointer | 80 | 80 |  |
| OK | Table S2 | rule verdicts 16,476 + author verdicts 80 = 16,556 | 16556 | 16556 |  |
| OK | 3.7 / Table S2 | unit-boundary author verdict: entry points 51 = 15 + 36, sync 29 | (51, 15, 36, 29) | (51, 15, 36, 29) |  |
| OK | 3.7 / Table S2 | judgment lists: other module / other unit / sync = 15 / 36 / 29, sum 80 | (15, 36, 29, 80) | (15, 36, 29, 80) |  |
| OK | 3.7 | other-unit groups: libfc 16, efct 10, dvb-core 4, i915 3, gdmulte 2, dm-snapshot 1 | [16, 10, 4, 3, 2, 1] | [16, 10, 4, 3, 2, 1] |  |
| OK | 3.7 | sync groups: dm iterate_devices 22 + 7 others | (22, 7) | (22, 7) |  |
| OK | 3.7 / 5.10 | kernel-module-boundary author verdict: entry points 15 | 15 | 15 |  |
| OK | Table S2 | the 80 call_arg functions = at80_src.json = the judged functions | (80, True, True) | (80, True, True) |  |
| INFO | Table S2 | random 50 of the AT-only pairs (seed 2026): tags |  | {'export_addressable_only': 48, 'select_phi_ret(+)': 2} | the 2026-11-09 draw was 49 EXPORT by-products + 1 phi/select (no information) |
| OK | Table S3 | UAFX pairs / unique / in FPEA / WL-only | (5899, 5118, 4912, 987) | (5899, 5118, 4912, 987) |  |
| OK | Table S3 | WL-only: IOCTL_CAND declared / defined, INT_HANDLER_T declared | (547, 289, 151) | (547, 289, 151) |  |
| OK | Table S3 | external pairs 698, most redundant ata_scsi_ioctl 91 units | (698, 91) | (698, 91) |  |
| OK | Table S3 | external unique names / defined in drivers / outside drivers | (359, 355, 4) | (359, 355, 4) |  |
| OK | Table S3 | outside drivers/: compat_ptr_ioctl etc. | ['blkdev_compat_ptr_ioctl', 'compat_ptr_ioctl', 'hpet_rtc_interrupt', 'snd_pcm_lib_ioctl'] | ['blkdev_compat_ptr_ioctl', 'compat_ptr_ioctl', 'hpet_rtc_interrupt', 'snd_pcm_lib_ioctl'] |  |
| OK | Table S3 | FPEA identifies in the defining unit | 9 | 9 |  |
| OK | Table S3 | not identified in the defining unit: static-call trampolines / registered in another unit | (4, 342) | (4, 342) |  |
| OK | Table S3 / S6 | other-unit registered: link layer recovers / inter-module | (304, 38) | (304, 38) |  |
| OK | Table S3 | defined-in-unit 289 = tracepoint by-products 25 + real ioctl handlers 264 | (25, 264) | (25, 264) |  |
| OK | Table S3 / S6 | real ioctl handlers: link layer recovers / remain | (224, 40) | (224, 40) |  |
| OK | 5.3 / S6 | shared handlers: row sums (342+264 / 304+224 / 38+40), by name (total / link recovered / remaining), names in both rows, unique functions of the 987 | (606, 528, 78, 372, 304, 68, 234, 414) | (606, 528, 78, 372, 304, 68, 234, 414) |  |
| OK | 5.3 | whitelist-side errors: tracepoint 25 + static-call 4 + outside drivers 4 | 33 | 33 |  |
| OK | 5.10 | inter-module examples remain unrecovered | True | True |  |
| OK | Table 12 / 5.5 axis 1 | fpea14 = fpea16 on the LLVM 14 bitcode | (129967, 129967) | (129967, 129967) |  |
| OK | Table 12 / 5.5 axis 1 | differing units / only14 / only16 / label diff / defined diff | (0, 0, 0, 0, 0) | (0, 0, 0, 0, 0) |  |
| OK | Table 12 / 5.5 axis 1 | units compared | 15522 | 15522 |  |
| OK | Table S3 heavy | unit-layer WL∖FPEA 987 breakdown (kind|class: n) | {'IOCTL_CAND|external_declared': 547, 'IOCTL_CAND|defined_not_FPEA': 289, 'INT_HANDLER_T|external_declared': 151} | {'INT_HANDLER_T|external_declared': 151, 'IOCTL_CAND|external_declared': 547, 'IOCTL_CAND|defined_not_FPEA': 289} |  |
| OK | Table 2 auxiliary heavy | C3-only used only by iterator-type APIs | 677 | 677 | definition: every call taking the address as an argument matches ITER (fp_audit.py regex); the earlier 726 is not reproducible |
| OK | Table 2 auxiliary | iterator share % | 0.52 | 0.52 |  |
| OK | 5.10 ath12k | 6.9 mac unit FPEA / C1 in @ath12k_ops | (45, 34) | (45, 34) |  |
| OK | 5.10 ath12k | 7.1.4 ath12k .o.bc / mac unit C1 / ath12k_mac_op_* defined | (48, 0, 40) | (48, 0, 40) |  |
| OK | Table 14 tlclk | cleanup_module C2 / tlclk_interrupt C3 | (True, True) | (True, True) |  |
| OK | Table 14 tlclk | UAFX (unit): tlclk_interrupt INT_HANDLER_T, tlclk_read READ_HDR, cleanup_module missed | (True, True, False) | (True, True, False) | the earlier miss result is from the KASAN build output |
| OK | Table 14 docg3 | docg3_release C1 / UAFX 0 | (True, '') | (True, '') |  |
| OK | Table 14 tlclk | unit defined functions 28 = entry points 28 | (28, 28) | (28, 28) |  |

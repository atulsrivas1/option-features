# author4 STATUS (M3a fixtures, independent Tester)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Status: authored, run only against the author's own reference code (m3a_ref.py); not run against any implementation. SYNTHETIC, seed 20261030, stdlib only. Not committed.
Basis: origin/main ce880c8 (docs/m3a incl. R-103..R-161, owner decisions 1-5, store budget 768 MiB, 1 GiB hard per worker).

## Counts
- Structural: 157 rows (m3a_cases_structural.json; 144 + 13 fix-round-2 rows). Earlier 148 included 4 history-append convention rows (DCP2); DROPPED per R-160 and IO contract section 4 (history append and load stay the 6 M2 positions; convention_mismatch only at request position 17 and view read). Generator HP/DCP2 leftover removed.
- Aux: 45 (second instantiation of every pair and type-first row, plus 3 fix-round-2). Lane: 6.
- Perf/resource rows: 71 (m3a_perf_resource_rows.json), 3 samples, workload manifest; 14 gates in M3A_PERF_ACCEPTANCE.md equal M3A_GATE_BUDGETS.md (check_gate_table.py: OK).
- Mutants: 56 (48 effective, each caught by >= 2 rows; 8 equivalent swaps per PO) plus 10 infrastructure mutants in the perf rows. The 49th (history-append convention) went with DCP2.
- Selfcheck: all 208 rows agree with m3a_ref.py; pending-ruling rows 0.

## Coverage (rulings)
- R-152 iv_form (slot 13, ivform 11 rows), R-155 convention value/type codes (slot 13), R-160 convention_mismatch (request pos 17 after prior_not_before_cutoff; view read last), R-148 record-major load scan, R-124 None bid/ask valid, R-150 71 spots over 78 cutoffs.
- Unit decision (coordinator, pending owner review): 768 MB and 1 GB in docs/m3a are BINARY: 768 MB = 768 MiB = 805,306,368 B; hard 1 GB = 1 GiB = 1,073,741,824 B. All rows, thresholds and notes use these.
- Store: 7 series per name, 181,692 records, 485,896,320 B M2 layout (463.4 MiB) = 60.34 percent of the 768 MiB budget (805,306,368 B); 45.25 percent of the 1 GiB hard limit 1,073,741,824 B.

## Fix round 2 (R-162..R-177), applied
W08 181,692; R07 721 series; trailer_missing pair decoy now a `#TRAILER` line; 10 accept-side boundary rows; R-148 loadscan row (+aux); R-164 trailing-zero strike row; R-165 non-string direction row (out-of-range direction DEFERRED, no contract code). Open questions: none (R-148 text determines the code). Note: the requested "binary limit 1,073,741,824 B = 60.3%" does not compute (485,896,320 B is 45.25 percent of it); 60.3 percent is of 768 MiB; both stated above.

## Gaps
- Only the structural, lane and perf/resource families are in this set; the 911-row family counts of M3A_FIXTURE_REQUIREMENTS section 4 (surface, V1-V21, selectors, history reuse) belong to other authors.
- Open items X3, X5, X8, X12, X13, X14, perf P3/P5/P7: RULED R-163..R-171 (rows added where required; P3/P5/P7 are perf-doc changes not applied in this round). No `iv_form` default/echo rows beyond structural codes.
- No convention_mismatch row for a skew-type view series beyond the 2 view rows; no row for a record lacking the field when request is forward beyond the request rows.
- Scratch dirs out1, pq1, pf1, pf2, ../a4chk are outside the manifest.

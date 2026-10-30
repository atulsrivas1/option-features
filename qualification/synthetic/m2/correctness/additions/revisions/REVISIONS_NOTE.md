# Revisions to merged rows (store canonical line, PR 81)

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Ruling: the canonical store line carries the grid as supplied (no padding) and, for sparse records only, a grid_idx key right after grid; the record hash and
content hash follow from it. Result of the check (check_merged_store.py, run from this folder): all 47 merged store rows (m2_cases_store.json) reproduce under
the new rules, so no replacement rows are needed (0 revised rows). Only the additions rows with sparse records (M2A-STORE-006 and the sparse_hash rows) changed.

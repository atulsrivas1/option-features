# Handoff (keep under 60 lines; update after every merge)

Updated 2026-10-28. Read this, then STATUS.md, DECISIONS.md, the coordinator skill (.claude/skills/option-features-release-coordinator/SKILL.md).

## PO decision 2026-10-28: R26 stays PRERELEASE (Windows x64 cp312, partial Windows evidence)
- Release notes with full disclosures: docs/r26-variants/RELEASE_NOTES.md (see PR 51; Next item 8 is done once that PR merges). Scoped qualified label is a next-release gate; candidate13 stays the baseline.

## Where we are: candidate13 proposed (2026-10-28); R26 prerelease out
- Freeze record: docs/r26-variants/CANDIDATE13_FREEZE_RECORD.md (supersedes candidate12; its PR is not final until merged; independent freeze review of the record DONE: approve-with-conditions, conditions applied). index.json 518539dd...efac; 2647 rows in files, 5 N5 rows excluded by id, frozen 2642 (candidate12's 2614 byte-identical, +28 N5 rows, no new graphs). Audit approve; source and controller reviews approve-with-conditions (applied; hardened rerun byte-identical).
- Replay v10 (option-features 8951003, io e156963, workers 8795f3e): library 405/405, N4 49/49, graphs 306/306, I/O 1783/1783, workers 96/96 (38 partial); all exit 0. Flagged: 89 rows and 30 graphs (28 N5 added, none removed; assumption-2 rows and graphs confirmed encoding but still flagged pending PO acceptance). Controller review is partial (see record section 7). excluded_ids order IS compared literally (correction). Release label stays PRERELEASE.

## Earlier: R26 prerelease out; candidate12 proposed as the post-release candidate (2026-10-27)
- Freeze record: docs/r26-variants/CANDIDATE12_FREEZE_RECORD.md (supersedes candidate11; its PR is not final until merged; independent freeze review done: approve-with-conditions, conditions applied, independent re-run of the five v9 harnesses matched; audit approve): 2614 rows in files (2304 + 310 graphs), nothing excluded, frozen 2614 (candidate11 + 6 = 4 rows + 2 graphs). index.json 4e2f6428...
- Replay v9 at option-features 0f37caa / io e156963 / workers 8795f3e: library 405/405 (+2 skipped), N4 49/49, graphs 306/306, I/O 1764/1764, workers 87/87 (32 partial); all exit 0, no expected-to-fail. Mutation proof for all five harnesses (first graph mutation redone).
- Integer-op incomplete capture and /checkpoint, /config shape order ratified (inferred); rollup rows and missing-member rows now authored. Two-control fix (PR 42) and demo (PR 41, synthetic-only) merged.
- Flagged frozen-subject-to-regeneration: 61 rows and 30 graphs. Gaps G1 to G26 in the record. Rulings ratified by the Product Owner.

- Windows qualification (2026-10-27): PO decision PRERELEASE, Windows x64 cp312 partial Windows evidence, not qualified (docs/r26-variants/WINDOWS_PARTIAL_QUALIFICATION_RECORD.md; must-fix list there; python-flint LGPL-3.0-or-later needs a licence review). Release notes must include the candidate12 flagged rows and gaps. Decided, accepted by PO.

## Next
0. Independent freeze review of CANDIDATE13_FREEZE_RECORD: DONE (approve-with-conditions, applied); next coordinator freeze and merge. Then candidate14 (PO R27 rulings): lift exclusion of the 3 null-nondict rows, harness assertion for the extra-stream control row, re-issue filter, hashes, counts and release notes. PO to review: N5 rows flagged (proposed), assumption-2 confirmation, A>K disclosure, sorted-literal excluded_ids, nonexpected two-control rows as negative controls (the last three already PO-ruled; see DECISIONS.md).
OWNER ITEMS first (parked until the owner returns):
1. PyPI wheel permission for Windows qualification: APPROVED by the owner and done; python-flint 0.9.0, duckdb 1.5.6, setuptools 80.9.0 (win_amd64 cp312) downloaded, sizes and sha256 verified against PyPI (see docs/r26-variants/WINDOWS_PARTIAL_QUALIFICATION_RECORD.md).
2. Qualification scope.
3. Release acceptance and the qualified-vs-prerelease label. Criteria: Windows qualification passes; demo works (merged, synthetic-only); two-control fix landed (done); /checkpoint and /config coverage (done) or scoped out; every flagged id disclosed; owner accepts.
4. DONE: the pending-decision review is complete; all decisions are now PO-ruled (see DECISIONS.md, "PO ratification of pending decisions" and "PO rulings on the six items"); some rulings carry open conditions (items 9b-9e). No review items remain for the owner.
5. Worktree cleanup (.claude/worktrees in the three repos, including s24-freeze12 after merge).
Team items:
6. Independent freeze review of candidate12: DONE (approve-with-conditions, conditions applied). Next: coordinator freeze and merge of the record PR. Candidate13 supersedes it once its record PR is reviewed and merged.
7. Q4 and the narrower-rollup clause are SCOPED OUT with disclosure (PO R27 ruling, 2026-10-28); N5-restore-q3-dropped-with-extra-stream-added also scoped out. Reopen only on owner-supplied contract text.
8. Release notes finalization (record section 8 items; filter re-issued for candidate13 hashes, counts and the 5 excluded ids; draft kept in the private work folder).
8b. New fixtures for uncovered Q3 / field_set positions; code and codec changes land together (PO condition).
9. Regenerate the flagged rows, assumption-2 block first (18 rows/graphs plus the 9 held rows).
9b. A>K over merge identity_conflict (open condition): author a fixture first that fails on current code and passes after the workers change; no frozen row may change.
9c. PR 34 entries (open condition): regenerate the 6 rows and graphs under Reading B; order of excluded_ids not asserted.
9d. Two-control F4 fix (open condition): frozen rows byte-identical per v9 replay; new two-control fixtures must fail before the fix and pass after.
9e. Release notes must disclose that c-domain and c-completeness are untested (rollup-wider row removed).
9f. CP3 compatibility ratified: Q2 combined-defect order unspecified and not asserted; Q4 held.
9g. Assumption 2: the 9 B and 9 B3 rows already encode it in candidate12 (analysis finding, PO acceptance pending via PR 49 review); no regeneration needed, so the flagged-rows item 9 assumption-2 block is satisfied pending that acceptance; the 9 graphs were not separately inspected.

## variants2 backlog
- Contract-versus-code conflict: BOUNDARY_CONTRACT line 322 may mandate canonicalizing -0.0, while variants1 rejects -0.0 permanently. Resolve in variants2.
- -0.0 pinning row already exists: N4-premium-b64-negative-zero-price-rejected (invalid_scalar, stage 4); no new row needed, only the pointer flag remains (analysis finding, PO acceptance pending via PR 49 review).
- Before any "qualified" release: independent controller review.

## Gotchas
- Controller runs need absolute paths; contained run via python -I -B, never reuse a failed attempt dir.
- Add .gitignore for bytecode before any run; commit-then-remove leaks into branch history.
- Fixture-vs-contract triage before bending code; Sonnet (not Haiku) for storage/restore work.
- Pinned counts learned from a first run (workers partial 32) must be recomputed by a reviewer.
- A mutation that does not trip proves nothing: confirm the mutated field is one the harness reads.
- Check gh auth (atulsrivas1) before every push.

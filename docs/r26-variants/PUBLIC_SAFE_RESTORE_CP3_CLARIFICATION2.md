# R26 variants: restore CP3 order, missing stream and suffix checks (clarification 2)

Status: proposed, needs independent review and PO ratification, October 27, 2026. It supplements PUBLIC_SAFE_RESTORE_ERROR_PATH_CLARIFICATION1 and POST_R26_CLARIFICATIONS section 4 and implements PO_RULING_RESTORE_OPEN (2026-10-27). It freezes no fixture and changes no frozen row. Parts not decided by existing text are marked **proposed**.

## Q1. Order of the temporal rules and cut-cursor regression (PO ruling A)

Sentence to add to the restore clarification, replacing its open wording: "In CP3, order is: missing stream; root A>K `temporal_cut` at `/request/knowledge_K_ns`; cut-cursor regression in current index order; then all remaining temporal rules. A temporal error other than root A>K never pre-empts a cut-cursor regression."

- Consistency: three frozen rows (N4-restore-regression-after-equal-positions, N4-restore-compound-cursor-regression-then-identity-conflict, W3-restore-cursor-regression) pin cursor regression over a `temporal_cut` at `/request/operations/0/root_ids/1`. Treating only root A>K as preceding regression leaves them unchanged. Row bodies are not in this repo; this rests on the PO ruling and workers PR 8, which reports they pass.
- Wording note: Clarification 1 says "then the existing temporal rules (for example root A>K ...); then cut-cursor regression". This sentence narrows the temporal rules that precede regression to root A>K. It is a compatibility choice (see DECISIONS 2026-10-27), not the only reading of Clarification 1.
- Implementation: option-feature-workers main (PR 8, merge 82aac59) `_regression_after_temporal` lets only `temporal_cut` at `/request/knowledge_K_ns` through. It runs only once a cursor regression is found, and after the K-regression check (see Q2).

## Q2. Knowledge regression coexisting with another defect

Sentence: "When a `knowledge_K_ns` regression coexists with another CP3 defect, which error is reported is unspecified; only single-defect cases are pinned." W3-restore-knowledge-regression stays as frozen (`checkpoint_cut_mismatch` at `/request/knowledge_K_ns`). No combined row is authored; N4-plan-restore-knowledge-regression-versus-cursor-regression stays unauthored. Fixtures must not assert the order. (The code checks K regression before the cursor scan; that is an implementation detail, not contract.)

## Q3. Missing stream (dropped retained stream)

Sentence to add: "After CP0, CP1a, CP1b and CP2, if the current Request's cut cursors omit any stream present in the retained checkpoint's cursors, return `VariantValidationError('checkpoint_cut_mismatch','/request/cut_cursors')`. This check is first in CP3, before the root A>K temporal rule and cut-cursor regression. The worker translates it to `VariantWorkerError('input_invalid', cause_code='checkpoint_cut_mismatch', cause_path='/request/cut_cursors')`." Its place relative to Request shape, scalar and admission errors follows Clarification 1 (those precede it).

Verification, read-only:
- Worker translation: `variants1/errors.py input_invalid(exc)` maps any `VariantValidationError` to `input_invalid` with `cause_code=exc.code` and `cause_path=exc.path`. No new translation is needed. Confirmed.
- Code: `validate_restore` on workers main has no presence check; a dropped stream is silently accepted (POST_R26 section 4 says so). The cursor-regression scan compares only streams present in both.
- Convention: the existing restore pointers in the variants layer are `/checkpoint/producer_admission`, `/checkpoint/evaluator_cohort_sha256`, `/request/knowledge_K_ns` and `/request/cut_cursors/{i}/position` (i the index in the current Request list). Library admission has no cut-cursor rule. `checkpoint_cut_mismatch` is the code used for every restore cut failure, so the code follows convention.
- **Proposed**: the pointer. An absent cursor has no index i, so `/request/cut_cursors/{i}/position` cannot apply; the stream-level pointer is the list itself, `/request/cut_cursors`, with no index and no stream id. This matches the PO's report of the old flow engine, but that engine (`_monotonic`, `merge_flow_history`) is not on disk here and could not be verified. No text in this repo states the missing-stream code or pointer (POST_R26 section 4 item 2 says it is in private boundary text). Treat code and pointer as proposed until ratified.
- **Proposed**: with several dropped streams the error is reported once at the same pointer (it carries no stream id).
- Fixture: N4-restore-missing-stream-dropped-retained-stream may assert code and pointer only after this sentence passes independent review and PO ratification.

## Q4. Suffix checks (proposed, not ratified; the PO held this item)

Clarification 1 already lists "suffix stamped position and known-at admission" between cursor regression and immutable merge and says "existing new-stamped-position and known-at rules remain unchanged". No text in this repo defines them: library `admission.py` has only stamped-position uniqueness (`identity_conflict` at `/snapshot/{coll}/{i}/stamp/position`, stage 5) and no comparison against the retained cursor. Draft, all **proposed**:

1. "A suffix Execution or Quote revision whose stamped position is not strictly greater than the retained cursor position of its stream, or not strictly rising within the suffix for that stream, returns `checkpoint_cut_mismatch` at `/snapshot/{collection}/{i}`, i being the suffix item index. The first failure is reported, scanning collections in Snapshot declaration order and then ascending suffix index." The pointer style follows Clarification 1 (`identity_conflict` at `/snapshot/{collection}/{i}`). The code is an extension: no text says which code applies. "Strictly rising within the suffix" overlaps the existing uniqueness rule (equal positions are already `identity_conflict` at `.../stamp/position`); which wins is undecided. Position: after cursor regression, before immutable merge (Clarification 1).
2. Known-at not regressing against the retained per-stream maximum: **dropped**. No text found to cite (not in Clarification 1, POST_R26 or the library), and the PO named it the weakest.

No fixture row until item 1 is reviewed. Workers implement Q3 after review, and Q4 only after its own review.

## Frozen rows changed

None.

## Review notes (2026-10-27, independent review of this PR)
- Q1 pins only the order of cursor regression versus root A>K. The order of A>K versus the merge step (identity_conflict) is not verified: with A>K and no cursor regression, the current workers code (PR 8) runs the merge and may report identity_conflict where Q1's wording would give temporal_cut. Fixtures must not assert A>K versus merge until this is ruled.
- Q2 supersedes the still-proposed POST_R26 section 6 sentence "temporal wins over K regression"; it is consistent with the frozen row W3-restore-knowledge-regression.
- Q3 code and pointer are convention-only (checkpoint_cut_mismatch is the code of every restore cut failure); an index-free /request/cut_cursors pointer is not defined by any frozen row or text and remains a guess until the PO ratifies it. Q4 is a guess and remains a proposal only. No fixture or code may use Q3 or Q4 until the PO decides: Q3 (code, index-free pointer, report several dropped streams once or per stream) and Q4 (adopt at all, which code applies, whether identity_conflict or checkpoint_cut_mismatch wins for equal suffix positions).

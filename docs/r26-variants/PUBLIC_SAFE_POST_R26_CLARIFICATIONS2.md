# R26 variants: post-R26 clarifications 2 (draft for independent review)

Status: architect draft, 2026-10-27 (story S5), **proposed, needs independent review and PO ratification**. Docs only: no code, fixture, freeze or implementation authority follows, and no ruling below is ratified. It supplements PUBLIC_SAFE_POST_R26_CLARIFICATIONS.md (called "POST_R26" below) and changes none of the earlier documents. Item order follows the S5 brief.

Evidence base and its limit. Read: docs/r26 (FLOW_CONTRACT.md is the superseded flow candidate; MATHEMATICS.md; INDEPENDENT_FIXTURE_CASES.json), the five PUBLIC_SAFE_* clarifications, CANDIDATE5_FREEZE_RECORD.md, DECISIONS.md, and option-contracts variants1 schema.py (read only for the `Binding` record and the `t` text rule). Not available in this repo: the private variants boundary text ("section 13", the assumption texts), the private fixture rows, and the "quote-selector clarification" (R26_EVIDENCE.md names it; no file by that name is in the repo). Rulings that would need those are flagged. Library and worker behaviour is quoted from POST_R26, not re-read. "Settles" means: the row may be hardened (or un-excluded) once the ruling is independently reviewed, ratified, and any listed fixture or code follow-up is done.

## 1. Tie at r: rolling member order (POST_R26 2.4)

- Evidence: PUBLIC_SAFE_ROLLING_ENDPOINT_EVIDENCE_CLARIFICATION1: premiums and witnesses are kept "in (event_ns, admission_ordinal) order; member_ids and member_revision_ids follow the same order restricted to M"; r is the "strict positive endpoint". It also lists "two positive rows tied at r" as a case to distinguish. POST_R26 2.4 item 4 marked the order proposed only because it did not cite this sentence.
- Ruling: both tied positives are members of M (r is their shared event_ns, the interval is `(max(0, r - horizon_ns), r]`); `member_ids` and `member_revision_ids` are ordered `(event_ns, admission_ordinal)`, so the lower admission_ordinal is first. This is stated by the clarification text; the proposal is only that POST_R26 2.4 item 4 be upgraded from "proposed" to "clarification-grounded".
- Settles: N4-roll-two-positive-rows-tied-at-r and IDENTITY4-N4-roll-two-positive-rows-tied-at-r leave the watch list if the frozen row orders members by (event_ns, admission_ordinal); if it used another order (for example lexical id), both regenerate. Check needed: compare the frozen row's member order with this ruling.
- Fixtures needed: tie where admission_ordinal order is opposite to lexical id order; tie plus an older positive inside M; tie plus a known-zero row at the same event_ns (zero is not a member).

## 2. Binding and context for bucket-proof rows (assumptions 1 and 2)

- Evidence: the private assumption texts are not available. In the flow candidate (FLOW_CONTRACT, dependencies paragraph) bindings are added for "precisely those records" that are dependencies: a Binding attaches to a supplied record through its `input_binding_id`. A prior-day source Result is a derived record with no `input_binding_id`; the bindings of its supplied inputs are already carried by its own dependencies. DECISIONS 2026-10-23 corrected 16 representative rows for missing context dependencies as fixture defects, a different defect (a required dependency missing), not an extra Binding.
- Ruling (assumption 1): a bucket-proof row does not gain a Binding or context record of its own beyond the Bindings of the supplied records it actually consumes. No text attaches a Binding to a derived Result. The frozen A-positive-current row stands.
- Assumption 2 (the prior-day source Result gets Definition/context) is **not ruled here**: it concerns identity-bearing fields of a derived Result and needs the private boundary text. The PO must decide, or the text be checked.
- Settles: A-positive-current is hardened (leaves the watch list) on ratification. The 9 B-contract-session1 / B-pooled-* rows stay on the watch list for assumption 2 alone.
- Alternatives for assumption 1: (a) require a Binding for derived Results: cost is a library change, regeneration of A-positive-current and the 9 B rows, and a rule saying which Binding a derived Result takes (none exists); (b) as ruled: cost is that bucket-proof evidence stays as under-bound as the shipped library makes it, which the 393/393 library run already accepts.
- Fixtures needed: a bucket-proof row whose consumed inputs have two distinct Bindings (both appear, once each); a bucket-proof row consuming a prior-day Result (no extra Binding appears).

## 3. FEFF/Cf rejection pointer on rights (assumption 3)

- Evidence: `Binding` in schema.py is `... mode:E.mode rights:text`; the text rule (`unicodedata.category(c) not in ("Cc","Cf","Cs")`) matches FLOW_CONTRACT section 1 (`t`: NFC, no Cc/Cf/Cs). U+FEFF is category Cf. The UTF8_BOM clarification covers only a transport BOM at offset 0 and states it "does not reinterpret a character inside a JSON string" or relax the "scalar/NFC rules". DECISIONS 2026-10-23 already ruled the text rule excludes Cf.
- Ruling: a U+FEFF inside a `text` string is `invalid_scalar` at stage 4. The pointer is the pointer of the text field holding the string, with no character offset: for a Binding, `<pointer of the Binding>/rights`. Pointers never descend into a string. The row's expected result is rejection; its id word "ordinary" is a misnomer.
- Settles: N4-bom-fefff-inside-json-string-is-ordinary-character leaves the watch list if its frozen pointer equals `<Binding pointer>/rights` for the placement it uses (the freeze record says /envelope/payload/rights was chosen by analogy; check it against where the Binding actually sits). If it differs, regenerate. Ids are stable, so keep the id and add a note that the case asserts rejection.
- Fixtures needed: FEFF at start, middle and end of `rights`; FEFF in another `text` field (description) for the same rule; a leading document BOM stays `invalid_json` at stage 2.

## 4. F4 membership under incomplete capture; rolling envelope and the 4 undetermined rolling cases

Part A, F4 (F4-parent-capture-domain-misses-tail, F4-span-inclusive-endpoint-not-captured). The contract cannot decide; recommended ruling and costs follow.

- Evidence: MATHEMATICS "Expected-member closure" and FLOW_CONTRACT "No future-member erasure": an expected root with no visible revision makes eligibility unknown and the population incomplete. Both govern expected roots only. A visible root that is neither expected nor inside the covered capture domain is addressed by no text I can read. MATHEMATICS also says the kernel "verifies bindings and set arithmetic, not provenance".
- Recommended ruling (**proposed, contract silent**): such a root is not a member. It is listed in `excluded_ids` with a capture-exclusion reason and its dependencies stay in the proof; it adds to no count and does not complete the population; the population stays incomplete (`incomplete_capture`). Rationale: membership is defined by the certified population (expected set and covered domain), and counting an uncertified record would let it change a result.
- Alternative 1, a visible root is a member when visible: cost is that membership depends on what the feed happened to deliver, so replays with different capture give different members; it conflicts with the closure rule's intent.
- Alternative 2, an error (`identity_mismatch`, root outside the certified population): cost is a new error condition with stage and pointer to define; the F4 rows would then expect rejection.
- Settles: both F4 rows leave the excluded list under the recommendation, after the expected outputs are generated; they regenerate if the PO picks an alternative.
- Fixtures needed: root before the covered domain; root past the covered tail; root at an inclusive endpoint capture does not cover; the same root expected-but-not-visible (eligibility unknown) as contrast.

Part B, rolling envelope and the four undetermined N4 rolling cases (N4-roll-unresolved-below-lower-bound-with-known-r, -at-exclusive-lower-bound, -inside-window, -after-known-positive-endpoint).

- Evidence: the rolling clarification: "Any unresolved raw premium anywhere in the full session prevents certifying r and window membership and yields that envelope with premium_unavailable, including an unresolved row at or below the exclusive lower bound"; if r cannot be certified, "retain the already defined full-session envelope and labelled observed evidence; dependent window Metrics remain unavailable under the existing priority rules". POST_R26 2.2 and 2.3 (from code): no-r envelope has empty member lists and the endpoint control's event domain as interval. The same clarification's case list names "unresolved endpoint membership (including an unresolved row outside M with a known r)".
- Ruling (clarification-grounded): when any raw premium in the full session is unresolved, r is not certified, so each of the four cases yields the no-r envelope: `member_ids` and `member_revision_ids` empty, `member_interval` the endpoint control's event domain, window Metrics and signs unavailable with `premium_unavailable` (`incomplete_capture` first if capture is also incomplete), raw population kept in `premiums` and witnesses. "Known r" in a case name means the maximum observed positive endpoint, not a certified r. The four cases share one outcome and differ only in where the unresolved row sits relative to the observed endpoint.
- Settles: the four N4-roll-unresolved rows and their four IDENTITY4 graphs can be un-excluded after regeneration against this ruling (freeze record: 6 excluded graphs; the other 2 belong to the F4 rows). This changes the freeze counts.
- Alternative (a certified r despite an unresolved row below the bound): cost is amending the rolling clarification sentence, new fixtures, and a rule for how an unresolved row affects window membership.
- Fixtures needed: unresolved row below the bound with a positive endpoint; at the exclusive bound; inside the window; after the endpoint; each with capture complete and incomplete (priority).

## 5. G1: phase / checkpoint_phase on worker and library errors (17 rows)

- Evidence: PUBLIC_SAFE_RESTORE_ERROR_PATH_CLARIFICATION1 defines the worker error as `VariantWorkerError('input_invalid', cause_code=code, cause_path=path)` and the validation error as `VariantValidationError(code, path)`; neither names a phase. docs/r26 INDEPENDENT_FIXTURE_CASES.json uses `phase` only as a descriptive string beside code and path. The freeze record says the code exposes no phase.
- Ruling: the contract defines no normative error-object field for phase or checkpoint_phase. They are documentation-only fixture fields. They stay in the 17 rows as non-asserted metadata, renamed in the next candidate to a clearly non-asserted field (for example `doc_phase`) so no consumer asserts them; the rows stay "partial" and G1 is closed as "by design". Asserting on phase would need a new normative field.
- Alternative (normative field): add `phase` to both error types in the contract package, library, codec and workers. Cost: a contract change across three repos, a defined phase vocabulary (CP0-CP3, stage names), new fixtures for every error row (not 17), and possible effect on error identity hashes.
- Settles: G1 (2 E-checkpoint, 5 W3-restore, 3 W3-admission, 7 N4-restore) accepted by design. Fixtures needed: none beyond the rename, a manifest-only change.

## 6. Request-immutability restore rule (POST_R26 section 4 item 3)

- Evidence: the restore clarification lists the CP3 checks (shape, scalar, admission, missing-stream, temporal, cursor regression, suffix stamps, immutable merge) and contains no comparison of other Request fields with the prior Request. FLOW_CONTRACT binds the checkpoint to `prior_request` and `policy_sha256`, so a policy mismatch is an existing CP rule, not this one.
- Ruling: **reject**. The guess (every Request field other than `knowledge_K_ns`, `cut_cursors` and `emit` equals the prior Request) is not derivable from any text, would reject Requests the contract does not forbid, and needs an unspecified code and pointer. Restore keeps the checks in the clarification. POST_R26 section 4 item 3, and the placement sentence tied to it, are withdrawn.
- Alternative (adopt some immutability): cost is that the immutable field list must come from the private boundary text, with code, pointer and order defined and library and workers changed; any list without that text is a guess.
- Settles: no frozen row; it stops restore fixtures from exercising an invented rule. Fixtures needed: a restore whose current Request changes a non-K, non-cursor field and is accepted.

## 7. Zero binary64 price (RawBinary64Price `bp`)

- Evidence: MATHEMATICS: an execution has exact decimal price "p >= 0". POST_R26 section 9: `RawBinary64Price` is `bp` (finite, strictly positive), so zero is rejected at stage 4. The rolling clarification treats known-zero roots as real inputs, and premium is price times positive quantity times positive multiplier, so zero premium requires zero price.
- Ruling: **accept** a zero binary64 price. `RawBinary64Price` becomes `bn` (finite, nonnegative); negative, NaN and infinity stay rejected. `Binary64Multiplier` stays `bp`. Negative-zero bits follow the existing `bn` handling in schema.py (not re-read here; confirm before fixtures).
- Cost of the alternative (keep `bp`): known-zero roots cannot be expressed in the binary64 price form, the integer and binary64 forms disagree on the same economic input, and binary64 known-zero rolling cases are unreachable.
- Code follow-up (not here): change the token in schema.py and any check relying on positivity. Widening accepts previously rejected input, so any frozen stage 4 row that puts zero in a `RawBinary64Price` field would need regenerating; which rows (if any) is private and not checked.
- Settles: no watch-list row; unblocks zero-price binary64 fixtures. Fixtures needed: +0.0, -0.0, negative, NaN, infinity in a raw price; zero-price execution giving a known-zero root in session and rolling cases.

## 8. Lane control per-partition binding (PR 12)

- Evidence: POST_R26 section 5: a complete `lane_prefix` control covers a partition when its event_domain contains the closed interval from `scope.partition_start_ns` to the anchor; no Control field carries a partition binding.
- Ruling: **defer; no schema change now**. Keep the shipped coverage rule (one control may cover several partitions, by interval only). Fixtures must assert only whether a control's domain covers a partition's interval, never that a control is "for" a partition.
- Alternative (schema change binding a Control to a partition key): cost is a new Control field or variant in the boundary schema and codec, identity impact in all three repos, regeneration of every lane fixture, and a version question (variants1 is a released prerelease). Benefit: closes the case of a control covering a partition it was not issued for. Revisit if a real producer issues per-partition lane controls.
- Settles: nothing on the watch list. Fixtures needed: as POST_R26 section 5, with coverage decided by interval alone.

## Summary of effect on the freeze record

| item | ruling | rows settled (on ratification and checks) |
|---|---|---|
| 1 | order (event_ns, admission_ordinal), clarification-grounded | tie-at-r row and graph, if the frozen order matches |
| 2 | assumption 1 stands; assumption 2 not ruled | A-positive-current hardened; 9 B rows stay |
| 3 | invalid_scalar stage 4 at `<Binding pointer>/rights` | FEFF row, if its pointer matches |
| 4 | F4: not a member, excluded (recommended, contract silent); rolling: no-r envelope | 2 F4 rows and 4 N4-roll-unresolved rows plus graphs, after regeneration |
| 5 | phase is documentation-only | G1 closed by design (17 rows stay partial) |
| 6 | reject | none; withdraws a guess |
| 7 | accept zero (`bn`) | none; code follow-up |
| 8 | defer | none |

Needs a PO decision because the contract cannot decide: 4A (F4 membership), 2 assumption 2, and 7 (grounded in MATHEMATICS but changes a schema token); also 5 and 8 if the PO prefers a schema change. Items 1, 3, 4B and 6 follow from public text and need only review.

Not claimed: no code behaviour is verified here; the private boundary text and fixture rows were not read; no fixture asserts any ruling here until independent review accepts it and the PO ratifies it.

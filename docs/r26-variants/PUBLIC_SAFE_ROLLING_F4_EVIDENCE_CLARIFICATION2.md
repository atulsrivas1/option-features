# Rolling no-r envelope and F4 exclusion evidence: contract sentences

2026-10-27. Status: proposed, needs independent review and PO ratification. Docs only; no fixture, library or freeze change follows from this file alone.

Purpose: give exact contract sentences so the 6 rows that candidate6 masks can be unmasked: the 4 N4-roll-unresolved rows (Q1) and the 2 F4 rows (Q2), plus their 4+2 IDENTITY4 graphs. Sources: DOCS_REVIEW_P2P3 and PO_RULING_REPRESENTATION (private work folder, r26-20261027), ROLLING_ENDPOINT_EVIDENCE_CLARIFICATION1, POST_R26_CLARIFICATIONS (2.2, 2.3) and CLARIFICATIONS2 (4A, 4B), FLOW_CONTRACT lines 111-113 (group-row dependency union at 113, available_at rule at 113), MATHEMATICS lines 35-37 and 115. Nothing was executed.

## Q1a. Evidence.excluded_ids under the no-r envelope (needs PO choice; evidence favors B)

Applies when any raw premium in the full session is unresolved or capture is incomplete, so r is not certified and M is empty ("an empty window means only the no-r envelope").

The clause under dispute: "Evidence.excluded_ids retains known-zero roots and full-session roots outside M". POST_R26 2.2 restates it as "known-zero roots, capture exclusions and every full-session root outside M".

### Reading A (PO ruling): known-zero roots only
- Argument: "outside M" is meaningful only against a certified M; unresolved raw premium "prevents certifying r and window membership"; unresolved and known-positive roots stay visible in premiums and witnesses.
- Consequence for the 4 N4-roll-unresolved rows: excluded_ids is empty in all four (they contain no known-zero root); the unresolved and positive roots appear only in premiums and witnesses.
- Exact sentence (needs PO choice): "When r is not certified (no-r envelope), M is empty and Evidence.excluded_ids contains known-zero roots only; no root is listed as outside M. Unresolved and known-positive roots appear in premiums and witnesses, not in excluded_ids."
- Cost: a special case; library behaviour per POST_R26 (code adds every root outside M) would be a conformance defect to fix; excluded_ids no longer equals "full-session roots minus member_ids".

### Reading B (literal): every full-session root
- Argument: M is empty, so every full-session root is outside M. This keeps the single rule used by every frozen rolling row with a certified r: excluded_ids = known-zero and outside-M roots = all full-session roots not in member_ids. It adds no case and matches POST_R26 2.2 ("settled by clarification and code").
- Consequence for the 4 rows: excluded_ids lists every full-session root (positive, known-zero and unresolved) in (event_ns, admission_ordinal) order; the expected values of the 4 rows and their graphs change and are regenerated (rows are not yet frozen).
- Exact sentence (needs PO choice): "When r is not certified (no-r envelope), M is empty and Evidence.excluded_ids contains every full-session root, in (event_ns, admission_ordinal) order; member_ids and member_revision_ids are empty, and the roots' raw dispositions remain in premiums and witnesses."
- Cost: excluded_ids then lists unresolved roots whose disposition is unknown; the sentence therefore states that this is a membership statement, not a premium disposition.

### Frozen-row evidence (read-only, candidate5/6 generated files)
- Frozen no-r row: flow.jsonl F3-D-rolling-unresolved-positive-r-envelope (flow.jsonl is frozen in full: 174 of 174 rows in CANDIDATE6_FREEZE_RECORD; the row carries no freeze_excluded tag). Verified: its only root a is unresolved (missing_definition), r is null, member_ids is [], excluded_ids is ['a']. That is Reading B on frozen data and contradicts Reading A and the PO ruling that unresolved roots are not listed.
- Frozen certified-r rows (obligations.jsonl, N4-roll-excluded-positive-lower-endpoint and N4-roll-known-zero-inside-window, both UNFROZEN_CANDIDATE/complete in the generated file but ratified in the freeze): roots a,b,c; members [b,c] with excluded [a], and members [a,c] with excluded [b]. In both, excluded_ids equals full-session roots minus member_ids. The complete-empty rows do not discriminate (all roots known-zero); the certified-r rows and F3-D fit B.
- Consequence of choosing A: it changes frozen row F3-D (excluded_ids ['a'] becomes []) and needs a library change. B changes no frozen row and needs no library change; only the 4 masked rows (not frozen) get new expected values.

### Recommendation: Reading B (literal), needs PO choice; evidence favors B
It is more consistent with the frozen rolling rows (one uniform rule: excluded = not in member_ids; the frozen complete-empty rows, where every root is known-zero, do not discriminate and are satisfied by both) and with "an empty window means only the no-r envelope" (empty M leaves no root inside it). Reading A needs the extra argument that "outside M" is unassertable, which the text never states for excluded_ids. If the PO keeps Reading A, its sentence is the minimum addition and the library fix is required. Either choice unmasks the same rows; they differ only in expected excluded_ids.

### Regenerated values under B (4 N4 rows and their 4 IDENTITY4 graphs)
The graphs hash every field including excluded_ids, so under B the 4 IDENTITY4 graphs regenerate too, together with their rows. Roots are listed in (event_ns, admission_ordinal) order, as in each row's premiums:

| Row | excluded_ids under B |
|---|---|
| N4-roll-unresolved-below-lower-bound-with-known-r | [a, b, c] |
| N4-roll-unresolved-at-exclusive-lower-bound | [a, b, c] |
| N4-roll-unresolved-inside-window | [a, b, c] |
| N4-roll-unresolved-after-known-positive-endpoint | [b, c, a] |

Under A all four stay [].

## Q1b. available_at_ns for the no-r envelope

Exact sentence: "available_at_ns is the maximum known_at_ns over all Evidence.dependencies, including the capture and endpoint Controls and the raw execution and PremiumCore dependencies of every retained full-session root, including roots outside M."

This replaces reading the rolling clause as raw-execution/PremiumCore only. It matches every frozen rolling row (for example the later-known-zero-endpoint-witness row: raw max 24, available_at 52 from the capture Control) and MATHEMATICS 37 ("maximal contributing known-at", the economic value/status boundary). In the 4 rows the raw max is 15 and the capture Control is 52, so the value is 52. Independent of the Q1a choice.

No conflict with FLOW_CONTRACT line 113 ("available_at depends only on admitted contributing selected revisions/context/references/certificates, not future excluded ledger facts"): that sentence excludes future, cancelled or out-of-scope ledger facts that are not contributing. The roots, PremiumCore records and Controls above are K-visible, admitted and contribute to the status/value of the row, so the maximum over them is the economic status boundary of MATHEMATICS 37. No future excluded record enters the maximum.

## Q2. F4 (visible root outside the certified capture domain)

### Q2a. Exclusion representation
Exact sentence: "A visible root that is outside the certified capture domain is not a member and contributes to no count; it is listed in Evidence.excluded_ids and adds one Dependency on the root's execution revision with use = \"exclusion\". No separate reason field is added; the population stays incomplete (incomplete_capture)."

Status of the token: existing convention (frozen span rows and F4-cancel-plus-new-relocation), now stated in the contract. Grounds: CLARIFICATIONS2 4A, FLOW_CONTRACT line 113 (dependencies include all supplied execution revision records, "including future/cancel/excluded roots to prove selection"), MATHEMATICS 115 (excluded hashes carried apart from causal operands).

### Q2b. Amended dependency scope
Exact sentence: "For such a root, add the exclusion Dependency on its execution revision; add no PremiumCore, witness, sign or count dependency for it; every other Evidence dependency is unchanged."

This amends the PO ruling's "nothing else stays" (not in any clause) to the reviewer's contract-supported wording: other dependencies of the result (context, economic, capture, policy) are untouched. The no-PremiumCore part rests on 4A ("adds to no count") and, by analogy, MATHEMATICS 35 (no payload inspection of a root that cannot contribute).

### Q2c. F4 available_at_ns
Exact sentence: "available_at_ns is the maximum known_at_ns over all Evidence.dependencies, including the exclusion Dependency." Immaterial to the rows: the exclusion dependency's known_at_ns (13 parent row, 22 span row) is below the other dependencies' maximum (capture Control 54 and 53), so any reading gives the same value. Retain the build-time assert: exclusion known_at_ns <= max over the other dependencies. This also does not conflict with line 113: the excluded root's revision is visible (not future) and, because of the assert, never raises the maximum above what the contributing Controls already set.

## What each sentence unmasks

| Sentence | Rows unmasked | Graphs |
|---|---|---|
| Q2a + Q2b (+ Q2c with the assert) | F4-parent-capture-domain-misses-tail, F4-span-inclusive-endpoint-not-captured (Evidence.dependencies for the excluded root) | 2 IDENTITY4 |
| Q1b | available_at_ns on the 4 N4-roll-unresolved rows | none alone |
| Q1a (either reading, after PO choice) | N4-roll-unresolved-below-lower-bound-with-known-r, -at-exclusive-lower-bound, -inside-window, -after-known-positive-endpoint (Evidence.excluded_ids) | 4 IDENTITY4 |

The 2 F4 rows and 2 graphs can be unmasked once Q2 is ratified; the 4 N4 rows and 4 graphs also need Q1a. If Reading B is chosen, the 4 rows are regenerated before unmasking.

## Not covered
Zero-price rows (blocked on the bn fix), work-item extras and any library change. Independent review and PO ratification are still required.

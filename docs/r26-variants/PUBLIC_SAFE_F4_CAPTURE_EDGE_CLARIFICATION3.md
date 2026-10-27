# F4 capture-edge cases: proposed contract sentences (items 1-3 of CANDIDATE9 UNDETERMINED)

2026-10-27. Status: proposed, needs independent review and PO ratification. Docs only; no fixture, library or freeze change follows from this file alone. Nothing was executed; code read only (merged PR 35, commit 4e87bc6).

Sources read: PUBLIC_SAFE_ROLLING_F4_EVIDENCE_CLARIFICATION2 (Q1a Reading B, Q1b, Q2a/Q2b/Q2c, ratified), PUBLIC_SAFE_POST_R26_CLARIFICATIONS2 section 4A (F4 recommended: not a member, excluded; contract silent), FLOW_CONTRACT line 113 (dependency union; available_at), MATHEMATICS lines 35-37 (closure, maximal contributing known-at) and 115, and the code: variants1/flow.py capture() lines 15-61, span.py _collect lines 52-76 and the excluded build at 134-137, current.py:39, integer_flow.py:22.

Grading: GROUNDED = follows from ratified/public text; CONVENTION-ONLY = matches code and frozen rows but no text states it; GUESS = neither.

## Item (a). F4 root that is also unresolved (missing definition / unresolved premium) in span

Current code: span.py:68-71 drops an F4 root (not expected, not inside every control event_domain) in `_collect` before `_premiums` is called (line 72), so it is never evaluated: it cannot enter `wit`, so it is not in `unres_ids` (span.py:134) and cannot produce `unresolved_premium`. It reaches `excluded` only through the memo at span.py:137 and takes the exclusion dependency only. flow.py:46-59 is the same: the F4 loop appends to cap.excluded and cap.excl_revs only; premiums_for runs on cap.raw, which never holds it. Capture is incomplete (flow.py:58; span via the domain check at line 128).

Proposed sentence: "A visible root outside the certified capture domain is excluded before premium evaluation: it is listed in Evidence.excluded_ids only, it is never reported as unresolved (not in unresolved_ids, no premium diagnostic), it does not change status from incomplete_capture to premium_unavailable, and it adds only its exclusion Dependency, whatever its definition or premium state."

Support: CONVENTION-ONLY, resting on Q2b (GROUNDED for "no PremiumCore, witness, sign or count dependency"): a root with no PremiumCore dependency has no premium disposition to report, so "also unresolved" has no evidence to stand on. No text says the status stays incomplete_capture; that part is the convention.

Alternative: also report unresolved. Cost: needs a PremiumCore/definition dependency for the root (contradicts Q2b), a premium evaluation of an out-of-population root (MATHEMATICS 35: no payload inspection of a root that cannot contribute), and a precedence rule between incomplete_capture and premium_unavailable; code change in span.py and flow.py.

Unlocks: a new span row (F4 root with missing definition inside the anchor window) and its IDENTITY4 graph; no existing row changes. The parent/flow variant is covered by the same rule at flow.py:46-59.

## Item (b). Several capture controls with different event domains

Current code: a root is covered only if every control event_domain contains it: flow.py:56 and span.py:68-69 use `all(...)`. An uncovered root takes F4 treatment. Note cap.domain (flow.py:23) is `cap.controls[0]["event_domain"]` when no interval is given, so the expected-root exclusion at flow.py:42 tests control 0 only, while the F4 loop tests all controls. That asymmetry is a code inconsistency for expected roots outside a later control's narrower domain: such a root is a member (not excluded) although outside that control's domain. Completeness is separately `all` (flow.py:24, span.py:128).

Proposed sentence: "With several capture Controls on an operation, a root is inside the certified capture domain only if it is inside the event_domain of every such Control (the intersection of the domains); a root outside any one Control's domain is outside the certified capture domain and takes the Q2a/Q2b exclusion treatment in parent, span and flow, whether or not it is expected."

Support: CONVENTION-ONLY leaning GROUNDED. A population is certified only where every Control certifies (complete, captured; flow.py:27-29; completeness is already a conjunction over controls), which is intersection. The ratified wording "outside the certified capture domain" does not say how several domains combine; intersection is the reading consistent with the existing conjunction but is not stated.

Alternative: union (any control). Cost: a root covered by control 1 only would be a member although control 2 certifies only its own domain; completeness over the union could be claimed with a gap between domains; the existing `all` completeness test would contradict the membership test. Needs reversing flow.py:56 and span.py:68 and every frozen multi-control row.

Open code point (not a sentence): the expected-root exclusion at flow.py:42 should test the intersection, not controls[0]; propose fixing in the same change if ratified.

Unlocks: needs new fixture machinery (op with two capture_ids); would unlock new parent and span rows (root in one domain, outside the other) with IDENTITY4 graphs. No existing frozen row asserting different-domain controls was found; existing rows are unaffected.

## Item (c). Rollup interval wider or narrower than the capture domain

Current code: rolling and rollup callers pass interval= (current.py:39 interval=full session; integer_flow.py:22 interval=op["rollup_interval"]). Then:
- cap.domain is the rollup interval (flow.py:23); it replaces the control domain as member interval, and an expected root outside it is an ordinary exclusion (flow.py:42-43, normal exclusion chain).
- Completeness requires every control event_domain to contain the rollup interval (flow.py:24-25). Rollup wider than a control domain gives incomplete capture.
- The F4 test uses the controls own event_domain, not the rollup interval (flow.py:56). So a non-expected root inside the rollup interval but outside a control domain is F4 (excluded, incomplete). A non-expected root inside the control domains but outside a narrower rollup interval is not F4 and is not listed at all. A non-expected root outside both is F4.

Proposed sentences: "F4 exclusion is tested against the event_domain of the capture Controls (intersection, item b), never against rollup_interval or any other caller-supplied member interval. A root inside the capture domain but outside rollup_interval is an ordinary window exclusion when expected, with its normal dependencies, and is neither listed nor depended on when not expected. When rollup_interval is not contained in every Control event_domain, the capture is incomplete (incomplete_capture), as the code now does."

Support: GROUNDED for the completeness sentence (closure: the population is complete only if the certified domain covers the window); CONVENTION-ONLY for "F4 tests the controls own domain" (the contract says capture domain; the rollup is a caller query, not a certification); GUESS for "not listed when non-expected and outside the interval" (no text says whether non-expected roots outside the query window are listed; it follows from F4 being defined only against certification and matches code).

Interaction with Q1a/Q1b (rolling): in a no-r envelope Q1a lists every full-session root in excluded_ids. An F4 root is listed once and carries only the exclusion Dependency, so Q1b maximum must not add its raw/PremiumCore dependencies. Proposed: "Q1b maximum covers the retained roots dependencies only; an F4 root contributes its exclusion Dependency alone." This reconciles Q1b (every retained full-session root) with Q2b by stating that an F4 root is not retained.

Alternative: F4 tests the rollup interval. Cost: a root inside the control domain but outside a narrow rollup would be F4 (incomplete capture) merely because the query is narrow, so a complete capture is reported incomplete; a rollup wider than the domain would never produce F4 in the gap; changes flow.py:56 and every rollup row.

Unlocks: new rolling and rollup rows (rollup narrower than domain with a non-expected root between; rollup wider than domain with a non-expected root in the gap) and the unresolved-F4-in-rolling combination; no frozen row asserts these. CANDIDATE9 item 3 ("regardless of rollup_interval") is covered by the first sentence above.

## Summary

| Item | Code (file:line) | Sentence status | Rows unlocked |
|---|---|---|---|
| a | span.py:68-72, 134-137; flow.py:46-59 | CONVENTION-ONLY (Q2b grounds the dependency part) | 1 span row + graph |
| b | flow.py:56, 23, 42, 24; span.py:68, 128 | CONVENTION-ONLY leaning GROUNDED; needs flow.py:42 fix and two-control fixture machinery | parent and span rows + graphs |
| c | flow.py:23-25, 42, 56; current.py:39; integer_flow.py:22 | completeness GROUNDED; F4 domain CONVENTION-ONLY; unlisted non-expected GUESS | rolling/rollup rows + graphs |

Needs independent review and PO ratification before any row is authored.

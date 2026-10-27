# Addendum 5: premiums and signs of an integer op under incomplete capture

Append-only addendum to PUBLIC_SAFE_INTEGER_INCOMPLETE_AND_RESTORE_SHAPE_CLARIFICATION4 (merged, not rewritten). Status: **ratified by PO 2026-10-27 (inferred)**, decided, pending owner review. Support: **CONVENTION-ONLY, inferred**; no contract text states it.

Sentence: "Under incomplete capture, the Result still lists the ordinary premium objects and signs of the retained roots (for an integer op as for a b64 op); only the metrics and weights change."

Basis:
- Frozen row F3-D-incomplete-raw-capture is the only frozen incomplete-capture directional row. It is a b64 session op, NOT an integer op; it shows the b64 behaviour only, and the integer case is an inference from it.
- Ratified F4 text: a retained root (inside the capture domain) remains a witness; only roots outside the domain are excluded, and exclusion is a membership statement, not a premium disposition.

Library check (read-only, variants1/integer_flow.py and flow.py `capture`): the result is SUPPORTED for the integer op. `directional_i64` builds a premium object per root in `cap.raw` (the retained population) and a sign witness per root, and returns them as `premiums` and `signs` regardless of `cap.complete`; under incomplete capture only `i64_metrics` changes (all ten metrics unavailable/incomplete_capture, `integer_weights` []). Roots excluded by F4 are not in `cap.raw`, so they carry no premium object or sign.

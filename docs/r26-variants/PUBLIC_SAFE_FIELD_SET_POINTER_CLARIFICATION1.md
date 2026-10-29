# Public-safe field_set missing/extra pointer clarification 1

Status: **ratified by PO 2026-10-27 (inferred from frozen rows).** The field_set parent pointer is INFERRED (the contract states no explicit rule); independently reviewed, recorded as "decided, pending owner review". Docs only; no code, fixture or freeze changed by this document. Supersedes the "proposed ruling" in POST_R26_CLARIFICATIONS section 1 (same direction, made definite and with corrected evidence).

## 1. Ruling

For a closed record that fails the stage-3 key-set check, `field_set` (stage 3) is reported at **the pointer of the record that fails (the parent), never at a member**. The pointer never contains the missing or extra member name.

| Position | Pointer reported |
|---|---|
| Envelope payload record | `/envelope/payload` |
| Direct-API root record (`/snapshot`, `/request`, `/checkpoint`, `/config`, ...) | the root string supplied by the caller |
| Record nested as a field | the field path, e.g. `/rec/f` |
| Record as an array element | the element path, e.g. `/rec/f/2` (actual index) |
| Record selected by a tagged union | the union object path (the same object that carries `kind`) |
| Union object with no `kind` member | the union object path (not `<path>/kind`) |
| Envelope with a wrong key set | `/envelope` (unchanged) |
| Duplicate JSON key | unchanged: stage 2, first duplicate key pointer |

Missing and extra give the same pointer, so "missing before extra" decides only which condition is reported when a record has both, and is observable through nothing but the pointer-independent order below.

## 2. Order

1. Pre-order, depth first: a record's own key-set check runs before any of its members are examined, so a parent `field_set` precedes any child error, including child errors at earlier declaration positions.
2. Within one record: any missing member (declaration order) is reported before any extra member (supplied order). Since the pointer is the record, the choice of which member does not change the result; the rule is stated so the condition is deterministic and so a `field_set` is never reported for an extra member of a record that also lacks one.
3. Records are visited in declaration order of fields and array index order (FLOW_CONTRACT line 39, stage 3 text). The first failing record wins.
4. A null value for a nullable member is present, not missing. A non-dict value is `type_mismatch` at the record pointer, before any key-set check.
5. Union object order: not a dict -> `type_mismatch` at the union object; no `kind` -> `field_set` at the union object; non-string `kind` -> `type_mismatch` at `<union>/kind`; unknown `kind` -> `invalid_scalar` (stage 3) at `<union>/kind`; otherwise the selected record's key-set check (missing before extra) at the union object.

## 3. Stage

Stage 3 for every case above. The contract's wording is "extra/missing keys are reported before scalar decoding" (stage 3 shape check), which also fixes the order versus stage 4. Only duplicate keys are stage 2.

## 4. Grounding

- Contract (FLOW_CONTRACT lines 39 and 41): fixes code `field_set`, stage 3, and the order "extra/missing keys are reported before scalar decoding"; it states no pointer rule for missing or extra, so the ruling is inferred from the frozen rows and the single-shape argument. The only pointer rule it states for `field_set` is for duplicate keys (their first duplicate key), a different condition, so it does not govern missing or extra.
- Frozen evidence (section 5): every stage 3 missing/extra row (782) asserts the parent record pointer.
- Single normative shape: library, codec, workers and direct callers (evaluate, checkpoint, execute call `validate_shape` with their own roots) must report one pointer; a pointer that names the member would also need JSON Pointer escaping of an extra key containing `/` or `~`, which the current `_ptr` does not do. A parent pointer needs none.
- Envelope key-set errors already point at `/envelope`, the record that fails; this makes every position uniform.

## 5. Frozen-row evidence (candidate6 generated fixtures, read-only, counted by code, stage and pointer form; no row content copied)

All `field_set` rows across every generated file (only `wire.jsonl` and `obligations.jsonl` contain any):

| Rows | Stage | Pointer asserted | Form |
|---|---|---|---|
| 751 `W3-field-*-missing` (99 record types; 30 of them drop `kind`) | 3 | `/envelope/payload` | parent, missing, payload root |
| 1 `W3-wire-missing-field` | 3 | `/envelope/payload` | parent, missing |
| 1 `W3-wire-extra-field` | 3 | `/envelope/payload` | parent, extra |
| 2 `W3-wire-*` envelope key-set rows (extra envelope key before a bad value; isolation) | 3 | `/envelope` | envelope parent, extra |
| 9 `W3-union-*-missing-kind` | 3 | `/envelope/payload/rows/N/payload` | union record in array element (N = 0 or 2), missing `kind`, parent |
| 9 `W3-union-*-missing-value` | 3 | same | array-element record, missing, parent |
| 9 `W3-union-*-extra-field` | 3 | same | array-element record, extra, parent |
| 1 `W3-wire-duplicate-before-schema` | 2 | `/envelope/schema_version` | duplicate key, first duplicate (not missing/extra) |
| 1 in `obligations.jsonl` (N4-bom) | 2 | `/envelope/schema_version` | duplicate-key rule, not missing/extra |

Stage 3 missing/extra rows total 751 + 1 + 1 + 2 + 27 = 782; all assert the parent pointer; none asserts a member pointer. The 751 `W3-field-*-float` rows are `type_mismatch` at the member pointer and are not field_set evidence.

Verified: "30 drop kind" is correct (30 of the 751 missing rows name `kind`, 30 record types); the nine nested `missing-kind` rows add the nested case.

Positions covered by frozen rows: missing at payload root; extra at payload root; missing and extra for a record inside an array element (including index > 0); missing `kind` of a union at the payload root and in an array element; envelope key set. No row contradicts the ruling.

Positions **not** covered by any row (the only ones needing new fixtures): a missing or extra member of a nested record that is a plain field (not an array element); a union with no `kind` that is a plain field of a record; an array of records nested inside a record other than the payload root (deeper than payload/rows/N/payload); a record with both a missing and an extra member (missing-before-extra); extra member order (first extra in supplied order) when several are extra; direct-API roots (`/snapshot`, `/request`, ...) since all rows enter through the codec.

## 6. Code change needed (library; not made here)

File `packages/option-contracts/src/option_feature_contracts/variants1/schema.py`:
- `_check_record`, stage 3 key-set block: both `fail("field_set", _ptr(path, f), 3)` (missing) and `fail("field_set", _ptr(path, k), 3)` (extra) become `fail("field_set", path, 3)`. Keep missing loop before extra loop.
- `_check_one`, union branch: `fail("field_set", _ptr(path, "kind"), 3)` for a missing `kind` becomes `fail("field_set", path, 3)`. `type_mismatch` and `invalid_scalar` on `kind` stay at `<path>/kind`.
- Update library unit tests that assert child field_set pointers; add the fixtures in section 5.

Becomes unnecessary: `option-feature-io` `packages/io/src/option_feature_io/variants1/codec.py` `_shape` (the `exc.path.rsplit("/", 1)[0]` re-point for `field_set` stage 3); `encode_record` and `decode_record` call `validate_shape` directly. The re-point is also unsafe for an extra key containing an unescaped `/`, which disappears. Direct callers in `option-features` (`evaluate.py`) and `option-feature-workers` (`checkpoint.py`, `execute.py`) change from child to parent pointers with the library fix; check their tests for asserted child pointers. Sequence: land the library change and the codec simplification together so the codec never double-trims.

## 7. Not ruled / open

- Nothing blocks the rule. The contract states no `field_set` pointer rule for missing or extra members (FLOW_CONTRACT line 41 gives only the stage-3 ordering "extra/missing keys are reported before scalar decoding", and the duplicate-key pointer, stage 2); the ruling is inferred from the frozen rows (section 5) and the single-pointer-shape argument.
- Fixtures to add are only the uncovered positions listed at the end of section 5.

## 8. Correction notes for earlier documents

Earlier documents say the "1,502 frozen field_set rows" expect the parent pointer. Only 751 of the 1,502 W3-field rows are field_set rows (the other 751 are `type_mismatch`); the parent pointer is supported by 782 stage 3 rows in total (section 5). Documents: DECISIONS.md 2026-10-23 entry (line 12), PUBLIC_SAFE_POST_R26_CLARIFICATIONS.md section 1 lines 13 and 16, and R26_EVIDENCE.md line 25 ("field 1502" is a row count, not a field_set count). Notes are appended to those documents in this change.

R27 note on item 5: a `kind` member that is null is a non-string `kind` and gives `type_mismatch` at `<union>/kind`.

# Public-safe field_set missing/extra pointer clarification 1

Status: **proposed, needs independent review and PO ratification.** Docs only; no code, fixture or freeze changed. Supersedes the "proposed ruling" in POST_R26_CLARIFICATIONS section 1 (same direction, made definite and with corrected evidence).

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
3. Records are visited in declaration order of fields and array index order (contract section 3 of FLOW_CONTRACT). The first failing record wins.
4. A null value for a nullable member is present, not missing. A non-dict value is `type_mismatch` at the record pointer, before any key-set check.
5. Union object order: not a dict -> `type_mismatch` at the union object; no `kind` -> `field_set` at the union object; non-string `kind` -> `type_mismatch` at `<union>/kind`; unknown `kind` -> `invalid_scalar` (stage 3) at `<union>/kind`; otherwise the selected record's key-set check (missing before extra) at the union object.

## 3. Stage

Stage 3 for every case above. The contract's wording is "extra/missing keys are reported before scalar decoding" (stage 3 shape check), which also fixes the order versus stage 4. Only duplicate keys are stage 2.

## 4. Grounding

- Contract (FLOW_CONTRACT section 3 and MATHEMATICS): fixes code `field_set` and stage 3, and the order "missing/extra before scalar decoding"; it is silent on which pointer. The only pointer rule it states for `field_set` is for duplicate keys (their first duplicate key), a different condition, so it does not govern missing or extra.
- Frozen evidence (section 5): every frozen row that asserts `field_set` for a missing member asserts the parent record pointer.
- Single normative shape: library, codec, workers and direct callers (evaluate, checkpoint, execute call `validate_shape` with their own roots) must report one pointer; a pointer that names the member would also need JSON Pointer escaping of an extra key containing `/` or `~`, which the current `_ptr` does not do. A parent pointer needs none.
- Envelope key-set errors already point at `/envelope`, the record that fails; this makes every position uniform.

## 5. Frozen-row evidence (candidate5 completion source, wire.jsonl, counted only; no row content copied)

The "1,502 W3-field rows expect the parent pointer" statement in DECISIONS (2026-10-23) and POST_R26 section 1 is **not accurate**. Counted by code, stage and pointer form:

| Rows | Code, stage | Pointer form |
|---|---|---|
| 751 (id ends `-missing`, 99 record types) | `field_set`, 3 | parent: `/envelope/payload` (751 of 751) |
| 751 (id ends `-float`) | `type_mismatch`, 3 | member pointer `/envelope/payload/<field>` (not a field_set row) |
| 0 | `field_set` for an **extra** member | none |
| 0 | `field_set` below the payload root (nested, array, union-selected) | none |
| 30 of the 751 missing rows drop `kind` (30 union record types) | `field_set`, 3 | parent (the union object, which is the payload) |

Consequences: the parent pointer is evidenced only for a missing member of the envelope payload record (including missing `kind`). The ruling for extra members, nested records, array elements and union-selected records is not frozen by any row; it follows from the single-shape argument above and needs new fixtures (POST_R26 section 1 fixtures list: missing first/last; extra before/after; missing plus extra; nested in array at index > 0; union without kind at nested position; envelope key set; duplicate key unchanged). No existing row contradicts the ruling.

## 6. Code change needed (library; not made here)

File `packages/option-contracts/src/option_feature_contracts/variants1/schema.py`:
- `_check_record`, stage 3 key-set block: both `fail("field_set", _ptr(path, f), 3)` (missing) and `fail("field_set", _ptr(path, k), 3)` (extra) become `fail("field_set", path, 3)`. Keep missing loop before extra loop.
- `_check_one`, union branch: `fail("field_set", _ptr(path, "kind"), 3)` for a missing `kind` becomes `fail("field_set", path, 3)`. `type_mismatch` and `invalid_scalar` on `kind` stay at `<path>/kind`.
- Update library unit tests that assert child field_set pointers; add the fixtures in section 5.

Becomes unnecessary: `option-feature-io` `packages/io/src/option_feature_io/variants1/codec.py` `_shape` (the `exc.path.rsplit("/", 1)[0]` re-point for `field_set` stage 3); `encode_record` and `decode_record` call `validate_shape` directly. The re-point is also unsafe for an extra key containing an unescaped `/`, which disappears. Direct callers in `option-features` (`evaluate.py`) and `option-feature-workers` (`checkpoint.py`, `execute.py`) change from child to parent pointers with the library fix; check their tests for asserted child pointers. Sequence: land the library change and the codec simplification together so the codec never double-trims.

## 7. Not ruled / open

- None blocking the rule itself. Open for review: whether the PO wants the evidence correction recorded in DECISIONS (751 missing rows, not 1,502 field_set rows), and the extra/nested/array/union fixture additions before any row asserts those positions.

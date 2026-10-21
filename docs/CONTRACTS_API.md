# Contracts source bootstrap

This source implements independently packaged `option-feature-contracts==0.1.0a1`
under `packages/option-contracts`. It uses only the Python standard library and
imports no numerical backend, I/O package or worker package. Source authoring is
not runtime, build, numerical or platform qualification.

The public module `option_feature_contracts` exports every frozen boundary record,
`R25_LIMITS`, `ContractValidationError`, `validate_limits`, `validate_record`,
`validate_snapshot`, `validate_request` and `validate_results`. The closed literal
schema is versioned implementation content; callers cannot register types.

`to_payload(value, limits=R25_LIMITS)` validates before producing JSON-compatible
content. `from_payload(record_type, payload, limits=R25_LIMITS)` accepts explicit
snake-case names (`snapshot`, `request`, `results`, `input_binding`, `result` and
the other declared record names), reconstructs exact typed records and validates.
Only I/O parses bytes and rejects duplicate JSON keys; passing an already parsed
dictionary cannot establish that its originating JSON lacked duplicate keys.

`canonical_bytes` returns bounded canonical **payload** bytes. `content_digest`
uses the `option-json1` domain; `record_digest` uses `option-record1`. Both require
the explicit matching record type. Canonical byte sizing walks the closed typed
schema before expanding the complete payload. Request lower limits must also be
applied to snapshot/results by their owning orchestration boundary.

Decimal admission uses the intersection of coefficient/exponent limits and the
1024-character/UTF-8 canonical-string limit. Projected canonical length is checked
from the bounded Decimal tuple before expansion. For example `1E1024` passes the
exponent cap but needs1025 wire characters and is rejected. Numerical certificate
export must translate an unrepresentable enclosure into per-output precision
failure rather than constructing an unserializable successful Result.

Tests in `tests/contracts/test_contracts.py` are authored but unexecuted. Under
the original EQ142 reservation no imports, tests, builds or installs run. Once
the coordinator admits runtime work, qualify Python3.12 in an isolated environment,
build the contracts wheel, independently record its source and SHA256, install
that wheel and run these tests against the installed artifact. Check absence of
the source tree on the import path. Repeat supported environment checks separately;
one platform never proves another. The reserved `_build_identity.json` package
data is generated only by controlled staging builds, never fabricated in source.

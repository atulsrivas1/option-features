# R25 contract preparation

Owner selected R25 after agreeing dedicated option repositories and independent versioned equity dependencies. [GOV037 #581](https://github.com/atulsrivas1/equity-features/issues/581), [E33 #526](https://github.com/atulsrivas1/equity-features/issues/526). These are source-only draft contracts, not frozen implementation admission or a package release. Owner approved independent R25 progression, superseding the blanket R18/EQ146 and EQ143/EQ144 acceptance wait. Reviewed frozen R25 contracts, compatible interface choices and story readiness gate implementation; R25 executor/resource, artifact/platform, numerical and integration qualification remain mandatory. EQ182 contract design is now In progress; the six dependent implementation/acceptance stories remain Backlog. No numerical qualification is claimed passed.

| Track | Repository | Existing stories |
| --- | --- | --- |
| Pure contracts and calculations | option-features | EQ182, EQ183, EQ184, EQ214 |
| Canonical input conversion and sinks | option-feature-io | EQ185 |
| Bounded orchestration and integration | option-feature-workers | EQ186 |
| Cross-repository acceptance | All three; canonical issue #532 | EQ187 |

Read [mathematics/model scope](MODEL_PROFILE.md), [canonical records](CANONICAL_RECORDS.md), [compatibility and blockers](COMPATIBILITY.json), [conformance cases](CONFORMANCE_CASES.json) and [layer handoffs](LAYER_HANDOFFS.md). Source-derived exact inventory stays private; nine of the 26 named option feature declarations are assigned to R25. Signed-versus-absolute delta and the activity-score-versus-summary distinction require explicit coverage records. Price/additional Greeks are foundation outputs, not extra coverage of the source's 26 declarations.

No initial package versions are published here. No historical adapter/worker is assumed compatible merely because its interface accepts a feature result. The accepted equity transport fixes quantity units to shares and input admission to a single instrument. Native option contracts/underlying identities require a reviewed option-owned result/codec/request boundary, with old equity schemas unchanged.

## EQ182 design packet

The current source candidate adds [decisions](DESIGN_DECISIONS.md), [nine feature bindings and residuals](FEATURE_BINDINGS.json), [native boundary specification](BOUNDARY_CONTRACT.md), [numerical qualification protocol](NUMERICAL_ACCEPTANCE.md), [independent fixture definitions](INDEPENDENT_FIXTURES.json) and [oracle protocol](FIXTURE_PROTOCOL.md). These documents and analytical expectations are proposed for independent review, not an executed fixture suite or frozen contract. A concrete forward-error method/qualification and actual local execution remain open before the affected numerical implementation can be accepted.

## Concrete method and source-authoring continuation

C04 now selects [option-arb-bsm1/version1](NUMERICAL_METHOD.md) with bounded Arb enclosures; the independent [oracle source](ORACLE_IMPLEMENTATION.md) uses mpmath and remains unexecuted. [Implementation admission](IMPLEMENTATION_PLAN.md) separates frozen-interface source authoring from producer integration/merge/release proof. [Manifest](CONTRACT_MANIFEST.json) pins the source definitions; coordinator exact-commit review/admission evidence on EQ182 determines the actual source-authoring freeze. Earlier candidate statements that method selection remained open describe the prior8ee545e snapshot; implementation/artifact/numerical qualification remains genuinely open.

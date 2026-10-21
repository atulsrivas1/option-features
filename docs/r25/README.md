# R25 contract preparation

Owner selected R25 after agreeing dedicated option repositories and independent versioned equity dependencies. [GOV037 #581](https://github.com/atulsrivas1/equity-features/issues/581), [E33 #526](https://github.com/atulsrivas1/equity-features/issues/526). These are source-only draft contracts, not frozen implementation admission or a package release. EQ146/R18 and reviewed story prerequisites still gate implementation; all seven implementation stories remain Backlog.

| Track | Repository | Existing stories |
| --- | --- | --- |
| Pure contracts and calculations | option-features | EQ182, EQ183, EQ184, EQ214 |
| Canonical input conversion and sinks | option-feature-io | EQ185 |
| Bounded orchestration and integration | option-feature-workers | EQ186 |
| Cross-repository acceptance | All three; canonical issue #532 | EQ187 |

Read [mathematics/model scope](MODEL_PROFILE.md), [canonical records](CANONICAL_RECORDS.md), [compatibility and blockers](COMPATIBILITY.json), [conformance cases](CONFORMANCE_CASES.json) and [layer handoffs](LAYER_HANDOFFS.md). Source-derived exact inventory stays private; nine of the 26 named option feature declarations are assigned to R25. Signed-versus-absolute delta and the activity-score-versus-summary distinction require explicit coverage records. Price/additional Greeks are foundation outputs, not extra coverage of the source's 26 declarations.

No initial package versions are published here. No historical adapter/worker is assumed compatible merely because its interface accepts a feature result. The accepted equity transport fixes quantity units to shares and input admission to a single instrument. Native option contracts/underlying identities require a reviewed option-owned result/codec/request boundary, with old equity schemas unchanged.

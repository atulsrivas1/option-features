# Candidate option-native canonical records

Draft option-canonical1. Owned in proposed independently installable option-feature-contracts, inside option-features repository. It is not a widened equity-feature-contracts schema and does not monkey-patch existing enum/dataclass registries. Actual public names, strict field types, serialization and error enums must be reviewed before implementation.

| Record | Required semantic fields |
| --- | --- |
| Definition | Contract ID, underlying ID, put/call, exact strike/currency, scalar deliverable/multiplier/action basis, exercise/settlement, last-trading/fixing/payment instants, expiry civil-date/timezone binding, definition revision/effective interval and known-at |
| Trade/quote | Contract identity; exact option price scale and quantity in contracts; event/known-at/source/order/revision; quote sampling and eligibility; absent/null/observed-zero and locked/crossed distinctions |
| Underlying/model references | Distinct underlying identity; spot units/currency/action basis; r/q/volatility/model facts with effective and known-at clocks; each independently optional according to requested output |
| Request/config | Selected output IDs; model/formula/schema/config version and hash; valuation/cutoff; exact definition/reference bindings; declared chain population/window and supported execution mode; solver/resource limits where required |
| Result per selected output | Contract/underlying/context identity, value/unit/scale or null, availability/status/reason, source/coverage/quality/evidence, supplied/computed origin, package/model/formula/schema/config versions and causal bindings |

Candidate result outcomes distinguish available, missing/incomplete/ineligible, unsupported_profile, invalid_input, nonidentifiable_inverse, bracket_exceeded, iteration_limit and numerical_failure. Malformed records/configurations are rejected atomically at their boundary. Freeze exception versus returned-status precedence and exact error schemas before Ready. Unrelated missing facts cannot invalidate an independently ready output.

The accepted equity BatchMetadata requires quantity_unit=shares; InputBinding/ResultMetadata/FeatureResult and SDK registry are closed exact types. Option quantities must stay contracts and underlying quantities stay shares. Do not hide native facts in opaque strings or coerce all identities to one instrument merely to satisfy legacy validation. A lossless compatibility mapping needs independent proof of every old invariant; none is established by this preparation.

Pure option contracts may depend on the qualified shared equity contract package; the option calculation package may depend on selected equity calculations. Neither equity calculation nor shared equity contract code imports options. Strategies can consume both without being imported by the lower-level packages. Numerical, data, wire and storage versions are distinct.

# R25 local qualification — current draft

Checkpoint: October 21, 2026. **UNRELEASED; release acceptance remains open.** Local builds/tests are merge evidence; hosted CI is optional. This report records observed component qualification separately from integration and release gates. Source-independent package behavior and mathematical contracts are unchanged by this documentation reconciliation.

## Qualified source and fixture identity

| Repository / distributions | Exact source commit |
| --- | --- |
| option-features / option-feature-contracts, option-features | `60aed608b2020764bff40d4cdfa434abbc2bde03` |
| option-feature-io / option-feature-io | `d893272f94e0967cc4a0ff965798a3e06439ad5f` |
| option-feature-workers / option-feature-workers | `153b73464e67d12d0e859b2061ded3c0c361b040` |

All four project distributions are `0.1.0a1`; native backends are exactly `python-flint==0.9.0` and `duckdb==1.5.6`. Frozen source-authoring contracts remain commit `9403854ff37a7c0b5dbc57c142893a1ce0a262e4`. A documentation amendment after these builds does not change an artifact's recorded source commit. Package/build inputs and test-source identities must remain unchanged to retain these receipts; a changed implementation requires fresh applicable evidence.

The independently reviewed successor wire fixture has SHA256 `37f79537ebbf69cd0f39d4f52745954ab6e9e90a0f486dca7e7bacdc5945eb23`: 111 result cases, 378 expected rows and 5 structural exception cases. Separate independent reviewer `/root/r25_wire_fixture_independent_review` reported 31,973 checks and zero findings. The original synthetic [fixture artifact](../qualification/fixtures/r25-independent-wire-fixtures.json) is retained publicly at those exact bytes. These empirical independent expectations are not rigorous Arb interval certificates; production enclosure claims retain their own method/evidence requirements. Fixture identity alone does not authenticate review; the coordinator retains the actual review and admission receipts.

## Source publication and selected output trace

Implementation source is merged, while release stories remain open: library main `05091f79a76d7154b40b4bacfad77bedb7bb358e` has tree `443a102067adbb89a79efe351bc6cfbb14a90bbf`; I/O main `29b4cf5f0fca9c4ed5e3f1d4c0a9aa3c6c947714` has tree `a163736d4b46a490229a0043e24d1a98e028a344`; worker main `2175ae247a1215e1370abc915d44b7f4d20b8e1a` has tree `2fa47033afcdbbf0331bec82c55e4181af6dd20c`. Each merged tree equals its qualified source tree. Library PR3 head `868c1275b1910380878e4259370b47f79a179639` only reconciled parents: qualified `60aed608...` and the contracts merge, without a content delta. None of these merges relabels the source identity of existing wheels.

| Selected outputs | Producer / story |
| --- | --- |
| DTE, moneyness, multiplier, spread, quote coverage, activity | [Reference calculations](../packages/features/src/option_features/reference.py), [EQ214](https://github.com/atulsrivas1/equity-features/issues/573) |
| Absolute delta, gamma; foundation price, signed delta, vega, rho, theta | [Forward model](../packages/features/src/option_features/model.py), [EQ183](https://github.com/atulsrivas1/equity-features/issues/528) |
| Implied volatility | [Inverse solver](../packages/features/src/option_features/inverse.py), [EQ184](https://github.com/atulsrivas1/equity-features/issues/529) |

This traces nine selected matrix outputs plus five foundation outputs, not the whole future option matrix. Six source stories are in Test. [EQ187 acceptance is In progress](https://github.com/atulsrivas1/equity-features/issues/532#issuecomment-6308139253), not complete.

## Reproduce independent fixture consumption

Use the public fixture with an installed, reviewed cohort and source checkout containing the qualification consumer. Example PowerShell from the library checkout (replace the interpreter placeholder with the clean qualified runtime; no implicit source installation):

```powershell
$env:R25_INDEPENDENT_WIRE_FIXTURES = (Resolve-Path qualification/fixtures/r25-independent-wire-fixtures.json).Path
$env:R25_INDEPENDENT_WIRE_FIXTURES_SHA256 = '37f79537ebbf69cd0f39d4f52745954ab6e9e90a0f486dca7e7bacdc5945eb23'
& 'QUALIFIED_RUNTIME_PYTHON' -B -m unittest discover -s tests/qualification -p test_independent_wire_fixtures.py -v
```

Independent [wire generator](../tools/generate_r25_wire_fixtures.py) and [mathematical oracle](../tools/generate_r25_oracle.py) use exact `mpmath==1.3.0`, pure-Python backend and separate 80/140-digit contexts without production imports. Fresh generation is a new candidate requiring independent review; platform/Python metadata or review receipt can change whole-artifact bytes. Do not regenerate and silently replace the admitted SHA. The raw original independent review receipt and command/environment evidence remain retained privately; their metadata/digest is not a claim that private receipts are publicly available.

## Executed local component qualification

| Local environment | Actual attempt | Artifact forms | Result |
| --- | --- | --- | --- |
| Windows x86-64, CPython 3.12.10 | Windows attempt-03 | Original wheels and wheels rebuilt from original sdists | 216 unittest executions passed; zero failures/errors/skips. |
| Ubuntu 24.04 / WSL, Linux x86-64, CPython 3.12.3 | Linux attempt-20261021-c | Original wheels and wheels rebuilt from original sdists | 216 unittest executions passed; zero failures/errors/skips. |

Each platform built all four project wheels and sdists from the exact sources above, rebuilt the original sdists and installed each form in separate clean pip-free runtimes. Each form ran 14 contracts + 48 features + 24 I/O + 14 worker component methods, plus 8 qualification methods: 108 per form, 216 per platform. The eight include the reviewed fixture consumer and seven consumer-assertion tests. The large fixture's cases/rows are not counted as separate unittest methods.

Runtime processes used `python -B`; installation suppressed bytecode generation. Independent fixture input and separately pinned digest were supplied via `R25_INDEPENDENT_WIRE_FIXTURES` and `R25_INDEPENDENT_WIRE_FIXTURES_SHA256`. Actual argv, working directories, source/archive/artifact hashes, environment inventory, exit codes and stdout/stderr remain in the coordinator's retained per-attempt receipts. The [public component evidence](https://github.com/atulsrivas1/equity-features/issues/526#issuecomment-6308022775) links this checkpoint to canonical delivery tracking. Example commands in API/qualification guides remain procedures, not substitutes for those exact recorded invocations.

Coordinator `/root` admitted all four platform/form artifact cohorts after source/build receipt, marker, wheel metadata/hash, installed inventory and native-license/notice inspection. Actual native wheel hashes were compared with official PyPI artifact hashes. This is source/artifact admission for local integration, not reproduction of upstream native builds, a legal opinion or final release acceptance.

Final-wheel tamper runs passed on both platforms. Windows first verified 253 installed files and completed real computation, then rejected each of seven separately mutated evidence/artifact cases on the next execution. Linux likewise verified 207 files and computed before rejecting all seven mutations. Linux tamper report SHA256: `001b618b1f20c5740160e38b288522a90c8c685a824e55c76930c645738eda2b`. These are cohort-specific observed checks, not a malicious-process security guarantee.

Separate package-layer isolation passed 172 additional methods on each platform across six fresh pip-free runtimes: contracts only (14), features + contracts + flint (48), and I/O + contracts + DuckDB (24), each for original-wheel and original-sdist-rebuilt-wheel forms. Exact installed closure/inventory and absence of unselected layers were checked. These additional executions demonstrate dependency separation; they do not add new matrix features or replace numerical/integration gates. Windows isolation receipt SHA256: `e09381727bcfa46473b2ff8555ad78225aa994921a50eb7fba1b72235bea22f7`.

The first Linux isolation harness aborted before tests because its preflight incorrectly required full-cohort module origins in a layer-only environment. This was a qualification-harness issue, not a production-package failure. The preserved attempt is not counted as a pass. A freshly reviewed corrected v2 helper retained source/grant/preflight safeguards and produced the successful isolated runs above; production sources and qualified artifacts were unchanged.

## Integration, portable artifacts and browser evidence

All four frozen five-scenario integration harnesses passed (Windows/Linux, original/rebuilt forms). The broader golden 111-case batch plus 111-case replay reports passed Linux original/rebuilt forms and Windows original wheels. **Windows rebuilt-sdist broad golden integration is still running and remains a mandatory gate**; no four-cohort broad integration completion is inferred.

A separate freshly reviewed direct/stored comparison now establishes full all-field parity for three cohorts: Linux original/rebuilt and Windows original. Fresh pure `evaluate` plus `encode_results` over all 111 cases/378 rows produced byte-identical complete payloads to each saved worker/readback payload, with completed-commit digest/count binding and fresh cohort verification. The retained `THREE_COHORT_FULL_PAYLOAD_PARITY.json` records these results. This is stronger than the integration harness's expected-field subset checks; the independent oracle consumer remains separate numerical proof. Windows rebuilt-sdist full payload parity remains pending, so no four-cohort claim is made.

Both portable v2 bundles passed fresh download, two-form installation, installed verification and five stored scenarios/45 rows on their own platform. Final wrapper ZIPs changed documentation only and preserve validated inputs: Windows SHA256 `3da16fc3ce5265da930f6a8e0cb0360bf541f5ebddf2d96dd98b91bcde4b5037`, Linux SHA256 `1f59147f0d806bdada80bfbf3193e0dfaed6d2772db930087583d34bed82c551`. Final coordinator/fresh-reviewer wrapper review remains pending. These hashes identify candidate local bundles, not a published release or automatic source-trust proof.

The external coordinator portable-manifest trust digests are supplied separately from bundle-controlled claims:

| Platform / artifact form | Trusted manifest SHA256 |
| --- | --- |
| Windows original | `84cdf8e215c5a2bc545afd9af5b4c15ef8bb6467ec213ab2591db1ce1e377c2f` |
| Windows rebuilt | `3314d2a41fb7fcc04c3a1f870c24235b2146eb78e8189e90f80c3c0605ddac17` |
| Linux original | `cb737c34273a3a33ebcd4c1d5bdec7eb8ad3c5235f2ae09b14cbdad777ea217d` |
| Linux rebuilt | `0f44b44cf393200636eac3f4d89123530bad5fbc8b0083e5a462faa60c4092bf` |

The coordinator actually inspected the browser demo through CUA: five stored-result tables/45 rows, plus a supplemental all-14-output price/IV round trip. Supplied sigma `0.2` returned IV `0.20000000001164153`. Screenshots and local evidence are retained for the stored demo and round trip. Complete Result parity was checked explicitly; this demonstration is integration evidence, not a separate independent numerical oracle.

## Remaining acceptance gates

Finish and inspect Windows rebuilt-sdist broad golden integration, complete final cross-platform canonical-byte comparison and final wrapper review, then reconcile release evidence and story acceptance. Source PRs are merged; six source stories remain Test and EQ187 is In progress. R25 remains UNRELEASED. Registry/tag/release publication is not approved by this report. Preserve historical receipts, source identities and owner publication boundaries.

## Superseded checkpoints and resource ownership

The EQ142 exclusive resource reservation was explicitly released after coordinator/independent process reconciliation. The original study's exit/outcome remains unknown/unaccepted; the release did not establish EQ142/R18/EQ146 completion or change their ownership. Bounded R25 validation uses its own environments. Historical active-hold language below in older handoffs describes source authoring, not the current runtime gate.

Earlier I/O attempt-01 failed at structural admission error conversion. Earlier fixture runs exposed a candidate-Vega comparison issue and noncanonical Decimal strings; reviewed successor corrections and exact-source rebuilt attempts supersede their acceptance status, not their retained failure receipts. Older Windows attempt-02/Linux attempt-b component passes used a previous library source and are historical, not proof for this cohort.

[Library PR](https://github.com/atulsrivas1/option-features/pull/3), [I/O PR](https://github.com/atulsrivas1/option-feature-io/pull/2), [worker PR](https://github.com/atulsrivas1/option-feature-workers/pull/2), [R25 epic](https://github.com/atulsrivas1/equity-features/issues/526).

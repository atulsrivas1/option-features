# R25 published release acceptance

Publication verified: October 21, 2026. The owner explicitly approved the prepared GitHub prereleases. All three `v0.1.0a1` releases are public, non-draft prereleases with the exact reviewed targets below. This supersedes the UNRELEASED/publication-pending wording in earlier dated qualification snapshots; their original build/source evidence remains unchanged. The [live Project](https://github.com/users/atulsrivas1/projects/2) and [R25 epic](https://github.com/atulsrivas1/equity-features/issues/526) remain lifecycle authority.

## Actual publication and readback

| Repository / release | Actual tag commit | Actual Git tree |
| --- | --- | --- |
| [atulsrivas1/option-features](https://github.com/atulsrivas1/option-features/releases/tag/v0.1.0a1) | `19d79f3354aa387ee025712a17335d1f10098536` | `4eb0183780f08ba872f5fa42d2de93b566dcb69c` |
| [atulsrivas1/option-feature-io](https://github.com/atulsrivas1/option-feature-io/releases/tag/v0.1.0a1) | `b77b3fa463e24cd320e8cd3b40dc2287d052f14a` | `811e9c07738e6b60f059f5eb6ee3f1f6d3a4b8fc` |
| [atulsrivas1/option-feature-workers](https://github.com/atulsrivas1/option-feature-workers/releases/tag/v0.1.0a1) | `15e68a226c7b21e6e1a9e7a12c5a3cbcf966582a` | `a6096ab77c60b77f2b806598336976fa9a6931e7` |

Each release contains the same four reviewed assets. The coordinator downloaded all twelve published assets afresh and checked their complete bytes, sizes and SHA256 against the approved packet. Fresh independent read-only reviewer `/root/r25_published_acceptance_review` separately checked the live non-draft/prerelease state, actual tag commit/tree, downloaded files and live GitHub asset digests with no findings.

| Asset | Bytes | SHA256 |
| --- | --- | --- |
| `R25-0.1.0a1-windows-amd64.zip` | 315223 | `3da16fc3ce5265da930f6a8e0cb0360bf541f5ebddf2d96dd98b91bcde4b5037` |
| `R25-0.1.0a1-linux-x86_64.zip` | 287784 | `1f59147f0d806bdada80bfbf3193e0dfaed6d2772db930087583d34bed82c551` |
| `R25_INDEPENDENT_WIRE_FIXTURES.json` | 1151065 | `37f79537ebbf69cd0f39d4f52745954ab6e9e90a0f486dca7e7bacdc5945eb23` |
| `R25_SHA256SUMS.txt` | 295 | `10aad6f97d90b58aa889e0328f74bf3c1d342ce68e4f88987373694e4f8177d9` |

The platform bundles contain the four own distributions in original-wheel, original-sdist and rebuilt-wheel forms. Native binaries are not bundled: exact official native wheel URLs/hashes and captured notices are included. External coordinator trust digests are published in [local qualification](https://github.com/atulsrivas1/option-features/blob/main/docs/R25_LOCAL_QUALIFICATION.md), separately from producer manifests. Upstream native builds were attributed and inspected, not locally reproduced.

## Qualified scope and retained proof

The first option release delivers nine selected matrix outputs plus five pricing/Greek foundation outputs within its admitted European BSM contracts. It does not claim the whole future option matrix. Calculations remain source-independent; I/O owns conversion/storage and workers own bounded orchestration. Supplied spot does not introduce an unused equity calculation dependency.

The actual qualified build-source commits remain library/contracts `60aed608b2020764bff40d4cdfa434abbc2bde03`, I/O `d893272f94e0967cc4a0ff965798a3e06439ad5f`, workers `153b73464e67d12d0e859b2061ded3c0c361b040`. Later documentation/tag commits do not relabel those existing immutable artifacts. Documentation-only deltas preserve all package/test/tool inputs and retained source markers.

Windows x86-64 CPython 3.12.10 and Ubuntu 24.04/WSL Linux x86-64 CPython 3.12.3 each passed 216 cohort plus 172 isolated unittest methods, seven tamper cases and both focused worker integration forms. All four original/rebuilt cohorts passed 111 independent result cases with identical retries and 111 replays. Fresh direct/worker/stored byte comparison established complete 111-case/378-row payload parity across all four forms. Aggregate receipt SHA256 `8e4f3d677bc60378dc38402aba724e48bcb7aeb2bb3d2db8ee7334fcf4946a9f`; the independent reviewer recomputed all eight underlying report hashes and complete case-array equality. No numerical suite was rerun merely to review publication documentation.

Both portable platforms passed fresh two-form installation, installed verification and actual separate-DuckDB stored scenarios. Browser inspection covered five scenarios/45 rows and the supplemental 14-output price/IV roundtrip (supplied sigma 0.2, returned IV 0.20000000001164153). The independently reviewed original synthetic fixture retains 111 result cases/378 rows and five structural exceptions at its exact published bytes. Empirical independent-oracle agreement, production enclosure evidence and roundtrip integration remain distinct proof domains. Retained failure/correction history remains in the qualification report.

## Lifecycle and boundaries

Publication/readback is complete. The epic and seven stories have actually moved Ready to release -> Released. Final Done/issue closure and milestone completion follow publication of this reviewed acceptance documentation; consult the live Project for the resulting current state. No CI completion is required under the owner's local-build/test agreement; fresh independent review and actual local proof were retained.

This publication is GitHub prereleases only. No PyPI, hosted service, production write, provider/private-data operation or performance claim was made. EQ142's exclusive resource hold was safely released after witnessed reconciliation, while its original interrupted study remains UNKNOWN/UNACCEPTED and its ownership is unchanged. R25 does not accept R18. No technical or publication work for a later option release is started by this acceptance.

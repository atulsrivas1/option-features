# Windows partial qualification record (2026-10-27)

Status: PRERELEASE. Windows x64, CPython 3.12.10 is PARTIALLY qualified. This is NOT a full Windows qualification and the word "qualified" must not be used for any release. Product Owner decision: decided, pending owner review. This record is public-safe: no fixture values and no private paths; it carries hashes, counts, deviations and gaps only.

## 1. Platform and method
- Windows 11 Pro 10.0.26300 AMD64, CPython 3.12.10, fresh virtual environments. Owner approved PyPI-only wheel downloads for this run.
- Source built from origin/main at option-features c0db18e, option-feature-io e156963, option-feature-workers 8795f3e (the controlled rebuild uses the same commits).

## 2. Third-party wheels (downloaded from PyPI; sha256 and size matched the PyPI JSON API)
| Wheel | Size (bytes) | sha256 |
|---|---|---|
| python_flint-0.9.0-cp310-abi3-win_amd64.whl | 9593474 | 8f1059536b7393e48b1444894c3b54ce1b961e4aa4a356e19217b26690f20db0 |
| duckdb-1.5.6-cp312-cp312-win_amd64.whl | 13190189 | 09ff51b230219f0d8b47fc8a1e17fb595ba9fab0c3d96a6de4d00b8ff86b3cf1 |
| setuptools-80.9.0-py3-none-any.whl | 1201486 | 062d34222ad13e0cc312a4c02d73f059e86a4acbfbdea8f8f76b28c99f306922 |

pip served them from its local cache of PyPI downloads; hashes were verified against PyPI regardless.

## 3. Project wheels
Built with `--no-build-isolation`, setuptools 80.9.0, no `wheel` package. The source record gives the sha256 of each project wheel but not the wheel file names or sizes; they are not invented here.

First build (git archive export, which applied eol conversion; superseded by the controlled rebuild below):

| Package | sha256 |
|---|---|
| option_feature_contracts | c1f8cce78f667b804aeeea043854a94173f97caa61aa5d29e3e9d2a9e69b4549 |
| option_features | bd6e17b0501e422cb2a132075d95f2bbcee9e12666128cf6bb28950216e9cbab |
| option_feature_io | a1caeeb1fae59a10414e98ae698979f71ba15abc45ed3132e4d7ca54692b2aff |
| option_feature_workers | 7724d44e92ee4978b6acfedbed0c70dc54e78d17056ae878609f81c1332fe99a |

Controlled rebuild (blob-exact staging, no eol conversion, `_build_identity.json` with the source commit written before build, fixed SOURCE_DATE_EPOCH): contracts 336119aa..., io 41fdd653..., workers 0cb39281..., features 3a4836d1... (sha256 prefixes only in the source record; full hashes live in the private run configuration). Wheels rebuilt from the new sdists are byte-identical (same sha256 for all 4). The only difference from the first build, besides the marker, is CRLF to LF: use blob-exact staging, not git archive with text=auto.

## 4. Results (counts)
- Clean offline install (`--no-index --no-compile`): closure = 4 project wheels + python-flint 0.9.0 + duckdb 1.5.6; modules load from site-packages.
- Unit suites on installed packages: contracts 14, features 48, qualification 8, io 24, workers 14 = 108 OK, no failures or skips. (The first qualification run failed only on a fixture hash because of eol conversion in the export; it passes with byte-exact files.)
- Candidate12 replay against installed packages: library 405/405 (2 workers-owned skips), N4 49/49, graphs bad=[] (4 mode graphs without a source row), I/O 1764/1764, workers 87/87 (55 full, 32 partial), 0 failed; identical to replay v9 counts. Two W3-admission rows still lack expected receipts.
- sdists built for all 4; rebuilt wheels identical (file inventory and per-file sha256).
- Path/storage (DuckDB 1.5.6, NTFS): create, reopen and atomic replace OK in paths with spaces, non-ASCII characters and 411 characters (system long-path support was evidently enabled; not tested disabled). Renaming an open DuckDB file was allowed on this machine, so do not rely on a lock for it.
- Integration: verifier checked 283 installed files; 5 scenarios (complete, unsupported, missing_spot, future_spot, partial_quotes) full parity, retry-idempotent, changed-source conflict rejected, replay parity; cancellation and bad-resource-config cases pass; unverified cohort rejected. Not a numerical oracle.
- Tamper: 7 reconstructed cases (installed file, wheel bytes, RECORD hash, source receipt, marker, unrecorded content, planted bytecode) plus 2 extras (module-origin shadow, wrong trust anchor) all rejected; control accepted.
- Layer isolation (pip-free venvs): L1 contracts 14 OK, L2 features 48 OK, L3 io 24 OK; closures exact, unselected layers absent, no bytecode.

## 5. Deviations (read these)
1. The trusted digest is NOT independent. No reviewed digest exists for this cohort; it was computed by a separate reimplementation and passed on the command line. This proves self-consistency only, not the external trust anchor.
2. Third-party source_commit values are stand-ins (sha1 of the wheel bytes), because upstream commits were unavailable offline; the receipts say so.
3. The seven R25 tamper cases are not enumerated in the repositories; T1-T7 are a reconstruction from the README categories. Equivalent, not original, harness.
4. The R25 broad golden integration (111 batch/retry plus 111 replay cases) and the stored demo/browser round trip were not run. Only the 5-scenario integration harness was run.
5. Layer isolation uses a simple equivalent harness and one artifact form, so 86 test methods rather than the R25 172.
6. Windows x64 CPython 3.12.10 only; no Linux parity.

## 6. Must-fix list before any "qualified" label
- Independently reviewed trust digest and receipts (coordinator-reviewed, not self-computed).
- Upstream third-party source commits (replace the stand-ins).
- The original R25 tamper and isolation harnesses, or an independently reviewed equivalent.
- Broad 111-case golden integration and the stored demo/browser round trip.
- Path tests not yet done: OneDrive-synced folder, antivirus lock contention, CRLF/BOM evidence files, long paths with system support disabled.
- Linux parity.
- A completed licence review of python-flint (section 7).
- Owner acceptance. The Product Owner qualified-release criteria also include the demo (merged, synthetic-only), every flagged id disclosed, and /checkpoint and /config coverage.

## 7. python-flint licence disclosure
python-flint 0.9.0 (win_amd64 wheel) is NOT MIT-only. Wheel inspection shows the licence expression MIT AND LGPL-3.0-or-later AND others with a GCC runtime exception, and bundled licence files for libflint 3.6.0, gmp 6.3.0, mpfr 4.2.2, the gcc runtime and winpthreads. duckdb 1.5.6 shows an MIT classifier and LICENSE. Wheel inspection is not a legal review. A licence review, covering LGPL-3.0-or-later obligations for redistribution of python-flint, is still required before any release that ships or depends on it.

## 8. Release notes must repeat the Candidate12 flags and gaps
Release notes must include the flagged rows and gaps from the Candidate12 freeze record: [CANDIDATE12_FREEZE_RECORD.md](CANDIDATE12_FREEZE_RECORD.md) (61 flagged rows and 30 graphs frozen subject to regeneration, gaps G1 to G26, open items, controller deviations), together with the deviations and must-fix list above.

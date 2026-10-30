# 2026-10-30 python-flint scratch install and the measured cost of the certified arb layer

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12.

Status: Developer/Researcher measurement, PO-directed. Docs only: no library code changed. This is measurement, NOT qualification evidence; the independent Tester has not reviewed it. Convention: this is the first file under `docs/decisions/` (one decision record per PR).

## 1. The scratch install (what it is and is not)
- Purpose: a clean interpreter with python-flint only, to measure the arb layer of the IV solver and to compare against the existing method-development environment. Scope: measurement only.
- Owner approved a python-flint install; the coordinator installed it into a scratch virtual environment outside the repo (session scratchpad, `flint-venv-parent\venv`; CPython 3.12, pip 25.0.1). Installed with `--no-index --no-deps` from a locally downloaded wheel kept in a separate download directory. Nothing was run from the download directory.
- Wheel: `python_flint-0.9.0-cp310-abi3-win_amd64.whl`, 9,593,474 bytes, sha256 `8f1059536b7393e48b1444894c3b54ce1b961e4aa4a356e19217b26690f20db0`. This equals the digest PyPI publishes for that file. Re-hashed by the Developer on 2026-10-30: same digest. Wheel tag inside the install: `cp310-abi3-win_amd64` (stable-ABI wheel, usable on CPython 3.10 and later, including 3.12).
- Wheel tag versus earlier records: the earlier Windows qualification (`docs/r26-variants/WINDOWS_PARTIAL_QUALIFICATION_RECORD.md`, section 2) lists exactly this wheel (same file name, size and sha256), and `docs/r26-variants/RELEASE_NOTES.md` (provenance section) states the same sha256 for python-flint on Windows. The "cp312" in the freeze and release records names the CPython 3.12 interpreter (and the duckdb wheel, which is a real cp312 wheel), not a different python-flint wheel; the python-flint wheel has always been cp310-abi3. So there is no cp312 python-flint wheel to compare against: the scratch install is the same wheel as before. Cross-check: `flint\pyflint.pyd` has sha256 `f1427349d712cb17a6aa1cd19dcce469417462fa66bd7edd6d049b5d11138a55` in both the scratch venv and the existing method-development environment, the five bundled DLLs (libflint, libgmp, libmpfr, libgcc, libwinpthread) hash identically in both, and both `WHEEL` files say `Tag: cp310-abi3-win_amd64`. (The CANDIDATE12 freeze record's owner-item shorthand "win_amd64 cp312" is ambiguous for the same set; it was not edited.)
- Provenance: the scratch install changes no pinned provenance. Pinned hashes, receipts and records are untouched.

## 2. What was measured and how
Merged main f5580cc. The solver is unchanged since the Stage 2 merge 1ac00cb (git log on inverse, arithmetic, model, floatfilter and chainiv shows no later commit): Stage 0 hoist, Stage 1 float filter and Stage 2 integer endpoints as shipped. Fresh worktree, `PYTHONPATH` to `packages/features/src` and `packages/option-contracts/src`. Host: the same machine as the earlier records (Intel Xeon Platinum 8160, 96 logical CPUs, Windows 11 x64, High performance power plan), one worker; other sessions may have been using the host. Workload: `tools/m1_chain_benchmark.py --sizes M --b6-sizes M --all-european --repeats 30` (size M, 2,000 contracts, every contract European, all quotes valid; this is the repo tool's all-valid-quote stand-in chain, not the Tester's chain). Two rounds each of the scratch venv and the existing method-development environment, interleaved (scratch, dev, scratch, dev). Per-solve timing and instrumented counts come from a scratch script outside the repo (wrappers around `chainiv.solve`, `inverse.price_interval/forward/bounds`, `model.enclosure_ends`, `FloatFilter.sign`, `floatfilter.make`); the instrumented run is a separate pass.

## 3. Measured figures (measured, flint 0.9.0 cp310-abi3, Windows x64, scratch venv)
Gates via the repo tool, size M, 30 repeats after one warm-up, p50 / p95, two interleaved rounds:

| Gate | scratch venv r1 | scratch venv r2 | dev env r1 | dev env r2 |
|---|---|---|---|---|
| B4 chain ATM IV | 0.022 / 0.026 s | 0.023 / 0.024 s | 0.022 / 0.023 s | 0.022 / 0.024 s |
| B5 30-day IV | 0.010 / 0.010 s | 0.010 / 0.011 s | 0.010 / 0.011 s | 0.010 / 0.011 s |
| B6 per-contract IV + ATM + 30-day (chain build included) | 2.289 / 2.418 s | 2.298 / 2.346 s | 2.301 / 2.393 s | 2.303 / 2.441 s |

B6 budget 5 s / hard 15 s: within budget in all runs. B4 and B5 are far inside their budgets.

Per solve (1,736 solves per `contract_iv()` call; 30 repeats, 52,080 solves per run), p50 / p95:

| | scratch venv | dev env |
|---|---|---|
| round 1 | 1.227 / 2.220 ms | 1.207 / 2.194 ms |
| round 2 | 1.177 / 2.142 ms | 1.181 / 2.149 ms |
| whole-chain `contract_iv()` p50 | 2.31 s, 2.22 s | 2.27 s, 2.22 s |

Arb calls per solve (counters outside results, one `contract_iv()` call, size M all-European chain): 22,879 arb enclosure calls over 1,736 solves = 13.18 per solve (price_interval 11.22, forward 0.96, bounds 1.00). B4: 11.31 per solve (16 solves). B5: 11.75 (4 solves).

Cost of each arb call (instrumented pass; the wrappers add about 6 percent: 2.44 s instrumented against 2.30 s plain):

| Item | calls | total | per call |
|---|---|---|---|
| `price_interval` (arb evaluation plus endpoint conversion) | 19,479 | 1.030 s | 52.9 us |
| of which endpoint conversion (`enclosure_ends`, Stage 2 path) | 19,479 | 0.340 s | 17.4 us |
| `forward` (vega, conditioning) | 1,664 | 0.198 s | 118.9 us |
| `bounds` | 1,736 | 0.138 s | 79.3 us |
| Stage 1 `FloatFilter.sign` | 62,380 | 0.114 s | 1.8 us |
| `floatfilter.make` | 1,664 | 0.023 s | 14.0 us |
| whole `solve` | 1,736 | 2.411 s | 1,389 us |

Shares of total solve time: arb calls (price_interval + forward + bounds) 56.7 percent; endpoint conversion inside price_interval 14.1 percent (the arb arithmetic in price_interval alone is 28.6 percent); float filter sign 4.7 percent; the remaining about 38 percent is Python logic outside the arb calls (acceptance test, exact-fraction compares, `Fraction.from_float`, result assembly).

Float filter versus certified fallback: 0 of 1,736 solves fell back to the fully certified path (every solve completed on the filtered path). Of 62,380 bisection float-sign checks, 42,901 (68.8 percent) decided the branch without an enclosure and 19,479 (31.2 percent) were undecided and went to an arb enclosure; 35.9 sign checks per solve. This is for this synthetic chain only; adversarial inputs reach the fallback more often (not measured here).

cProfile of one chain (`contract_iv`, 4.77 s under the profiler, which inflates everything about 2x; read as shares). Top by own time: `model.equation` 0.655 s (21,143 calls, arb arithmetic through the python-flint operators), `dyadic_endpoint_parts` 0.299 s own / 0.746 s cumulative (47,758 calls), `arithmetic._finish` 0.192 s, `math.gcd` 0.163 s (219,771 calls), `inverse._solve` 0.156 s own, `Fraction._from_coprime_ints` 0.150 s, `_discounted` 0.140 s own / 0.403 s cumulative, `FloatFilter._eval` 0.120 s, `Fraction.from_float` 0.105 s own / 0.308 s cumulative (64,863 calls). Cumulative: `_price` 1.920 s, `acceptable` 1.542 s, `enclosure_ends` 0.877 s, `_conditioning` 0.529 s, `bounds` 0.290 s.

## 4. Wheel-tag comparison
cp310-abi3 in the scratch venv against the existing method-development environment: same wheel, same pyd and DLL hashes, same tag. Timings agree within noise: B6 p50 2.289 / 2.298 s (scratch) against 2.301 / 2.303 s (dev); per solve p50 1.18-1.23 ms against 1.18-1.21 ms. No wheel effect exists. The requested "cp312 against cp310-abi3" comparison is therefore not a comparison of two wheels (section 1); the result is a replication of the existing environment, useful as a repeatability check.

## 5. Comparison with earlier recorded figures
| Item | Earlier record | This measurement | Note |
|---|---|---|---|
| B6 IV part, size M | 1.40 s p50, 1.53 s p95 (`docs/M1_CLOSE.md`, compute only; Tester 1.35 / 1.42 s) | 2.29-2.30 s p50, 2.35-2.44 s p95 (chain build included) | about 1.6x higher; not the wheel |
| Per solve after Stage 2 | 0.96 / 1.57 ms (DECISIONS Stage 2 entry; second pair 1.02 / 1.70) | 1.18-1.23 / 2.14-2.22 ms | about 1.2-1.4x higher |
| Arb calls per solve | 9.6 mean (Stage 2 entry); about 13 (other records) | 13.18 (B6), 11.3 (B4), 11.75 (B5) | matches the "about 13" figure; the 9.6 came from a different chain |
| B4 size M | 0.063 s p50 | 0.022 s | this run faster |
| B5 size M | 0.021 s p50 | 0.010 s | this run faster |

Differences are not caused by the wheel (identical binaries, identical timings across both environments) and not by solver code (unchanged since Stage 2). Probable causes, not proven: (1) a different chain: the earlier figures used the Tester's all-valid-quote chain or other stand-ins; this run's all-European chain needs 13.18 arb calls per solve against 9.6 on the earlier Developer chain, a ratio of about 1.4, which by itself explains most of the per-solve gap; (2) the earlier B4 and B5 figures may include other overheads or a different construction cost; (3) host load from other sessions. To close this: re-run the Tester's chain through the same environments.

## 6. Analysis: what dominates now, which levers remain
- Arb calls are still the largest block: 57 percent of solve time at 13.2 calls per solve. Endpoint conversion is now a minor part (14 percent of solve time, 17 us per enclosure) after Stage 2; the arb arithmetic itself is 29 percent. The float filter costs 4.7 percent and decides 69 percent of bisection steps, so it works; the 31 percent undecided steps (about 11 enclosures per solve) are near the root where a binary64 price cannot separate from the target, and that count is the number to reduce.
- About 38 percent of solve time is plain Python outside arb (acceptance test, Fractions, gcd, `from_float`). Cheaper acceptance and exact compares (integer arithmetic, fewer Fraction creations) change no enclosure and are the lowest-risk remaining speed-up.
- Fewer enclosures: a Newton (or secant) float seed that yields a tight bracket needing only a few certified enclosures instead of about 11 per solve would cut the arb block most (already named as the next lever; not built; the saving is a hypothesis until built and measured). Lazy ring / lazy ball construction (balls only when a decision needs them, and sharing the spot, rate and carry balls across the 2,000 contracts of one chain) is a smaller lever: `_discounted` is 0.140 s own and `ball_rational` has about 40k calls in the profile.
- The wheel is not a lever: no other wheel was tested and these numbers show no wheel sensitivity.
- B6 is 2.3 s against a 5 s budget on this chain (more than 2x margin); B4 and B5 have more than 40x margin. No budget is at risk from the arb layer on this workload.

Not done: the Tester's chain; adversarial chains; multi-worker runs; full-output B6. No library, test, provenance or HANDOFF change.

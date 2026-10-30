# Team meeting 2026-10-30: where we are and whether we are on the right track

mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

Chair: Product Owner. Present (roles): PO, Architect (docs author), Developers (stories A and B, solver, runner), Testers (independent), Fixture author, Auditor (tracker), Researcher (existing backlog, no new run). Called by the owner after the in-hand tasks were finished. All figures are synthetic workload, relative engineering budget, one Windows x64 host (2 x Xeon 8160, 48 physical cores), CPython 3.12.10, python-flint 0.9.0; no Linux claim; nothing is validated on recorded data.

## 1. Where we are

### 1.1 Release plan V3
| Release | State | Evidence |
|---|---|---|
| R27 | done | candidate15 (PR 59) |
| P1 | done, accepted | PR 63, 0.2.0a1, independent code review, 109 of 111 frozen R25 cases identical (the two that differ are the ruled change) |
| M1 | done, closed | PR 65-74; docs/M1_CLOSE.md; OC5, OC6, chain ATM IV, 30-day IV, solver Stages 0-2, opt-in default single-process runner |
| M2 | built; not closed | stories A and B merged (PR 79, 80, 88, 93, 98), matrix, budgets, fixtures (570 correctness + 298 additions rows), tracker; runner integration parked (below); close record not written |
| M3, M4, M5 | pending | 24, 21, 5 tracker rows; no matrix or fixtures yet |
| RQ | pending, last | adapter, display rights, recorded data, real-size budgets, Linux evidence |

### 1.2 Feature status (docs/FEATURE_STATUS.md, enforced by tests/m2/test_feature_status.py)
113 rows (81 design rows + 32 release items): done 40, partial 9, pending 63, dropped 1 (R28a as a separate release). Design rows: done 28, partial 9, pending 44. Done rows on the wire: 7; library-only: 31. "Done" means library module, independent fixtures, independent review, synthetic and Windows only. Pending by release: M2 2-3 (alignment follow-ups, runner integration), M3 24, M4 21, M5 5, RQ 7, later 4.

### 1.3 Performance, owner goal one (budgets B1-B12 and M2 gates)
| Gate | Budget / hard | Measured | Status |
|---|---|---|---|
| P1-T1 spread and touch stream | 100k records/s | 664k records/s p95 at 1e6 | met |
| B2 OC5 one contract | 50 us | 13 us p95 | met |
| B3 OC6 50 updates | 200 us / 1 ms | 114-127 us (Ticks), 175-181 us (strings) p95 | met; string path margin only about 10 percent: thin |
| B4 / B5 chain ATM / 30-day IV | 1 s / 1.5 s | 0.063 s / 0.021 s | met |
| B6 IV part, size M, all-valid chain | 5 s / 15 s | 8.62 s before, 2.80 s p95 after Stages 0-2 | met |
| M2-G0 full output set, one worker | 5 s / 15 s | p50 2.35-2.41 s, p95 2.58-2.66 s | met, about 2x margin |
| B7 whole workload | 170 / 240 min | M1 runner 2.38 min at 24 workers; M2 family all 8.91 min (parked branch) | met; developer runs, Tester re-ran scaling only |
| M2 store B1 append | 25k records/s | 69-87k p5 | met |
| M2 B18 trade-to-grid | 50k prints/s | 59-82k p5 | met |
| M2 B2n/B3n ratio (6,000 vs 2,000) | 3.6 budget, 4.0 hard | 3.2-3.67 paired median | pass hard; thin |
| M2 B16 worker start | 5 s / 512 MB at 2,000; hard 15 s / 1 GB at 6,000 | 2.5-4.0 s / 202 MB at 2,000; 7-12 s / 600 MB at 6,000 | hard met; budget missed at 6,000 (not gated) |
| M2 B13 store per series | 64 KB | 37-69 KB depending on measurer | thin |
| Ratio rules 1e6/1e5 (print families) | <= 12 | 9.6-11.7 | thin (F18 11.7) |
Caveats: synthetic generators we wrote; relative budgets; one host; B7 not independently re-run by a Tester; the 5-20x float-filter claim was never a target and the measured Stage 1 gain is 3.3x, Stage 2 about 3x, Stage 0 1.37x per solve (combined 3.1x on the gate chain, 8.62 to 2.80 s). The certified solver results are identical to the pre-change solver on every compared contract (about 370,000 solves in the Tester differential).

### 1.4 Order of work
Owner direction (V3): all features and indicators first on synthetic data; vendor adapter last (RQ). We are following it: no adapter, vendor or network work exists in the repo.

## 2. Are we on the right track
Honest assessment: yes on direction (library-first, synthetic-first, performance gates measured, independent fixtures and reviewers), no on cost: M2 took far more review rounds and PRs than the value of each round justified.
- Velocity: about 100 PRs merged in two days across the library and siblings; M1 closed in one long day; M2 built in a day and then spent most of the time on rule convergence. Roughly 60 percent (estimate) of M2 PRs are docs or fixtures about malformed-input and precedence rules.
- Main causes of the review churn: (1) the design is silent on many edges, so every independent fixture author surfaced 15-20 ambiguities and each needed a PO ruling, a docs PR, a fixture regeneration and a re-review (about eight docs rounds on the I/O contract); (2) authors and reviewers repeatedly read a stale checkout and rejected or rebuilt against old text; (3) rulings were issued one ambiguity batch at a time and then amended (the type-first rule changed the precedence story three times); (4) PR conflicts on DECISIONS.md and HANDOFF.md (every PR appends) forced extra rounds; (5) reviewers reopened scope (third-round docs reviews) and the Testers and developers measured with different methods (F7 ratio 1.7-2.2 versus 0.8-1.0, B3n protocol, B15 definition); (6) fixtures merged ahead of code twice left main red.
- Risks: nothing is validated on recorded data; every design-silent rule is an interim PO ruling pending the design session (requests 1-3, 6, 8, DR-M2-1, the whole M2 AMB set, the grid and store shapes); a late design answer regenerates fixtures; all measurements are one Windows host; the PO is a serial bottleneck; reviewers are the same model family as authors; the HANDOFF/DECISIONS files are append-only logs that now cost conflicts.
- Validated versus unvalidated: validated = behaviour against independently authored synthetic rows and differential oracles, certified-solver result identity, determinism across worker counts, many mutation checks. Unvalidated = real data shapes, Linux, vendor semantics, design-ratified meaning of interim rules, real-size performance, user-facing wording.

## 3. Process retro
Failures this stretch: fixtures merged ahead of the code that makes them pass (PR 90 before 88, PR 96 before 93: main red twice); fixes committed locally but never pushed (PR 79 fix, PR 93 head; caught only by a Tester running the old head); stale counts in the tracker (three refresh rounds); reviewers recommending deletions (scratch files, owner-only); a single PO deciding every ambiguity; developer evidence-only claims (corrected by Testers several times: B1 275k figure, B13 19.7 KB per series, fused reads speedup, F7 1.8-2.1 ratio, test-hook state); interim rulings changing fixtures; one runner clean-up script located processes by name (nothing was killed; the PID-only rule is reaffirmed).
Rules adopted: merge-order rule (fixtures after the code they need, or same PR, or expected-fail with a ticket; main never red; recorded in DECISIONS and the PR template); tracker enforcement test and PR template checkbox; verify remote heads with git ls-remote after every push; PID-only process control; independent author, reviewer and Tester roles; fixtures never edited, contradictions are defect reports; no deletions without the owner.
Rules needed: a review round cap (two rounds, then a bounded recheck of exactly the listed items, new findings become tracked follow-ups unless they contradict an accepted row); one ambiguity batch per release before fixture authoring starts, ruled once; one docs PR per release for contract text; a shared benchmark method document agreed before any gate is measured; DECISIONS/HANDOFF split per release or per PR file to stop conflicts (for example one file per PR under docs/decisions/, merged into the log at release close).

## 4. Proposals for the remaining work
- Split M3-M5 into smaller releases with their own matrices: M3a surface, term structure, skew (V1, V3-V10); M3b realized-vol join and history reuse (V11-V15); M3c frame builder without presets (V16-V22, proposed assignments); M4a open-interest outputs; M4b exposure and dealer-sign (labelled modeled); M5a shadow presets; M5b equity-side join. Each release: matrix and budgets, one ambiguity batch, independent fixtures, code, close.
- Parallelism: matrix and fixtures for release N+1 while release N code is reviewed; two developers on disjoint modules (as stories A and B), shared types published first; Testers re-run at the head that will merge.
- Fewer review rounds: ruled-ambiguity batch before authoring; round cap; one agreed method note per gate; the PO accepts on a checklist (rows, hashes, suites on the merge head, tracker updated, remote head verified).
- Researcher's accepted ideas and where they fit: float filter, process-pool runner, Stage 0-2: done. F7 density-adaptive window strategy and F17 sparse reads (strict prebuilt ratios 0.8-1.5 at 3x overlap): an M2 follow-up story, only if M3 consumers need them. Lazy ring/record creation (B16 start time and private bytes at 6,000 series): follow-up with the runner. Input synthesis sharing (about 23 percent of CPU at 48 workers): follow-up in the runner story. Runner scaling (S02 definition, N above 24, full hash matrix on the whole workload): finish with the parked runner PR. Newton bracket seed: deferred until a budget is missed. Python-flint measurement of the certified enclosure cost: waits on the owner's install decision.
- Stop doing: per-ambiguity fixture round trips; third and fourth docs review rounds; hand-typed counts; reviewers advising deletions; developers reporting numbers as gate results before the Tester measures.

## 5. Parked and tracked items
- Runner integration (branch m2/runner-integration, pushed, no PR): done: m2 and all families as units, M2BIN attach (new file per generation, content hash compare, gc.freeze), per-worker store memory with 1 GB hard limit, faults, perf_sut v3 for G0, B11, B12, B16, B17, B18 and D/E/C/R/S/K rows, 31 failing-first tests, docs. Measured at 24 workers (developer evidence): G0 per-unit p95 3.01 s, efficiency 0.89; B16 2,000 series 2.5-4.0 s / 202 MiB, 6,000 series 8.3-11.7 s / 603 MiB; B17 write 33.9k, read 75.4k records/s p5; B18 81.7k prints/s p5; B12 whole workload (1,950 units, family all) 8.91 min against 170/240; S01 scaling 4.9x at 4 workers. Not done: S02 trade-stream scaling, full hash matrix on the whole workload, B11 at 30 repeats, B1-B10 and B13-B15r bindings; about half a day plus a Tester re-run.
- Runner rulings needed: (1) rank fixture truth 7,440 versus 7,340 values (the manifest ranks 7,440 but the library drops 5 points per session by AMB-4: the library is right, the manifest should say 7,340: the fixture author corrects it); (2) S02 definition: unit-sharded (default) with a contract-sharded variant reported; (3) N above 24 for B12: allowed up to the cap, reported as informational.
- Totality follow-ups: (1) story A check_prints still raises on 78,859 of 600,000 hostile lists (test skipped): fix in a small PR; (2) build_tape on hostile contract records: the contracts map is trusted and adapter-validated (documented); (3) f17_columns and f17_sweep_columns are internal trusted entry points (documented).
- Other tracked: mutation-tool targets after code rewrites; trusted-contracts note in the I/O contract (added in this PR); design requests awaiting the design session; scratch and junk files in author and Tester scratch folders (owner-only to delete); python-flint scratch venv approval; B7 machine confirmation.

## 6. Questions for the owner
1. Python-flint install into a scratch venv (about 10 MB from PyPI): approve or decline (it unlocks the certified-enclosure cost measurement).
2. Which machine is the B7 reference (cores and RAM)? Today: 2 x Xeon 8160, 48 physical cores, 254 GiB.
3. Design-session ratification: can the design session take the interim rulings in one batch (requests 1-3, 6, 8, DR-M2-1, the M2 AMB set)? Until then every interim ruling can regenerate fixtures.
4. Approve the proposed split of M3-M5 into M3a-c, M4a-b, M5a-b and the review-round cap (two rounds, then a bounded recheck)?
5. Approve one decision-record file per PR (docs/decisions/) to stop the DECISIONS/HANDOFF conflicts?
6. Scratch and junk cleanup in the scratchpad folders and stale worktrees: owner-only deletions; approve a one-time cleanup by you or give explicit permission for a named list.
7. Is Linux evidence needed before RQ (WSL has no bash on this host; a process check would need an install)?
8. Keep fully independent roles (author, reviewer, Tester) on every PR, or relax for pure docs PRs?
9. Go or no-go to start M3a (matrix first, no code) after M2 close, or pause for your direction?

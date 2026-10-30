# Working agreement

> Working document, not a decision. Part of the portable playbook (`playbook/README.md`). Each agreement: **Rule**, **Why**, **Default**, **Alternatives we considered**, **Change when**. Record any change as a decision row.

**Two kinds of text, kept apart.** Lines marked **Owner agreement** record what the owner actually decided or stated. Lines marked **Suggested default (not an owner agreement)** are this playbook's own advice, added for reuse; the owner has not decided them. Unmarked "Default" lines restate the owner's agreement unless they say otherwise. Change or drop suggestions freely; change an owner agreement only by a new decision.

## 1. The owner is the facilitator only
- **Rule:** the owner does not decide routine matters and is not asked to approve PRs. The team works until nothing is left, then reports.
- **Why:** the owner wanted fewer questions and less token cost, and said "come to me only when there is nothing left".
- **Default:** owner reviews Release 0 once, may veto at a demo, answers owner-level items.
- **Alternatives:** owner approves every merge (slow, the early model); owner approves per release (kept only as a veto at the demo).
- **Change when:** the owner wants tighter control of a risky area; make that area an owner-level item rather than reverting the whole model.

## 2. Who accepts and who decides
- **Rule:** the PO accepts or rejects stories and releases; the Architect rules on technical matters; the coordinator decides routine matters. The coordinator merges after checks and PO acceptance.
- **Why:** one named decider per question stops both stalling and drift; an early session routed acceptance to the owner and was corrected.
- **Default:** as `TEAM.md`.
- **Alternatives:** the coordinator also accepts (rejected: the coordinator would review its own routing); developers merge their own PR after approval (allowed only where a repo's own AGENTS.md says so, until the Architect records an override; the charter's merge by the coordinator applies once the override is recorded).
- **Change when:** the team is one person: see "Solo or small team" in `VARIANTS.md`.

## 3. Escalation: what returns to the owner
- **Owner agreement:** only owner-level items go to the owner: pricing and plan numbers, data purchases and provider contracts, engaging a lawyer and any legal position, a new principle or a change to one, a real conflict between two owner rules, scope across gates, and a safety rule that cannot be kept (including any spend).
- **Why:** keeps the owner's attention for what only the owner can do.
- **Default:** one message, once, with item id, what it blocks, the provisional decision in force and a recommendation. Not repeated. Work continues on the provisional decision.
- **Alternatives:** batch all questions at the end (used for non-blocking items, via the release report).
- **Change when:** the owner adds items to the list (for example "any spend over X").

## 4. Three reviews before approval
- **Rule:** nothing is approved (PO accept or merge) until three reviews are recorded in the PR, none by the author: UI design review (Designer), architecture review (Architect), code review (independent; the other Developer for app code). Each PR carries the Review table; a verdict is approve, changes, or N/A with a reason a reader can check ("no UI file touched"). A "changes" verdict blocks until the reviewer has seen the fix. Where a review cannot be done, the reviewer writes "not verified: <what>" and the PO decides whether to accept with that limit.
- **Why:** a merge without the gate happened once; reviewers found real defects in nearly every PR (`OPERATING-LESSONS.md`).
- **Default:** order build, code review, architecture review, UI design review, Tester pass, PO accept, merge. Architecture and UI may run in parallel when findings cannot overlap; verdicts are recorded in order.
- **Alternatives:** one combined reviewer (rejected: not independent expertise); reviews only on code (rejected: contracts and UI drifted); retroactive reviews of already merged work (the owner chose to skip them and review as builders build against it).
- **Change when:** the product has no UI (mark UI review N/A with the reason each time) or no code in a PR (docs-only still gets an independent read).

## 5. Release acceptance
- **Rule:** after Release 0 the PO declares a release done when its exit criteria are met and all three reviews and the Tester pass are recorded for every story. The owner may veto within the demo. The next release does not start until the owner has seen the demo or said "go on". Non-build prep for the next release continues meanwhile.
- **Why:** the owner stays facilitator but keeps one veto per release.
- **Default:** as stated. A demo is not a launch and changes no status.
- **Alternatives:** owner sign-off per release (slow); no veto (owner lost the safety valve).
- **Change when:** releases are tiny; demo every second release.

## 6. Defects
- **Rule:** Testers record findings in the PR with severity: blocking (an acceptance criterion fails, data is shown dishonestly, a safety rule breaks, or an accessibility failure on role, name, keyboard or contrast), major, minor. A blocking defect stops the story until fixed and re-tested. A defect found after merge becomes a fix story at the top of the current backlog, pulled before new work. The PO may defer a minor finding with a written reason. Design change requests go to the design repo as a note citing story, board, contract.
- **Why:** one path for findings; the design repo stays the source of truth.
- **Default:** as stated. **Alternatives:** an external tracker (we used PRs and the backlog). **Change when:** volume needs a tracker; keep severity names.

## 7. Cost and limits
- **Rule:** idle roles do not run; the Researcher is capped; mechanical work (regenerating files, formatting, link and count checks, bulk edits) uses a cheaper model, judgment work (architecture, product rulings, contract reviews) the stronger one; a usage limit pauses the loop and resumes at reset, no retry loop; reviewers read the diff and the files they name, not the whole repo; parallel work only when independent; generated files are regenerated, not re-read; the coordinator rotates its own session before it grows heavy, writing `HANDOFF.md` first (what is Done, in review, the Ready buffer, open owner and human-only items). **Suggested default (not an owner agreement):** pick a rotation trigger you can measure (a turn count or a token count) and keep `HANDOFF.md` short enough to read at a glance.
- **Why:** token burn was the owner's recurring concern.
- **Default:** no daily token cap. **Alternatives:** a hard daily cap (not set; add if cost surprises).
- **Change when:** the owner sets a budget; make it an owner-level item and add a stop condition.

## 8. Test environment
- **Rule:** test on localhost against the mock adapter first, then the real API and data once supply is ready. No hosted staging unless the owner asks. Test accounts and labelled sample data only; never a real credential.
- **Why:** no hosting cost or credential exposure before it is needed.
- **Default:** as stated. **Alternatives:** hosted staging from day one. **Change when:** testers or demos need a shared URL.

## 9. Identity and access
- **Rule:** run the account switch (`gh auth switch -u {{owner-gh-account}}`) before any git or gh call; the owner trusts the repo once in the desktop app; no pushes to main; each agent uses its own worktree outside the shared checkout and removes it when done.
- **Why:** the CLI login flipped accounts mid-session; agents overwrote each other's checkout.
- **Default:** as stated. **Alternatives:** branch protection on main (the owner did not request it). **Suggested default (not an owner agreement):** turn it on, requiring the Review table and green checks, once any session has merged without the gate (`VARIANTS.md`). `gh auth switch` is global to the machine, so concurrent sessions share one login: assert the account before a push. **Change when:** a second human joins.

## 10. Human-only steps
- **Rule:** when a step only people can do (engage a lawyer, recruit participants, supply lists, restore a file, buy data, set prices), log it with its owner, report it once in the next report, keep working on all unblocked work, and stop only when nothing unblocked is left. No repeated reminders.
- **Why:** the owner is not nagged and the team does not idle.
- **Default:** as stated. **Alternatives:** stop at the first blocker (rejected: idles the team). **Change when:** an item stays blocked for several releases; raise it once more in the release report with the rework risk.

## 11. Reporting cadence
- **Rule:** one line in the coordinator's log per merged story. After each release: what shipped, demo script and result, list of "pending owner review" decisions, human-only items, Ready buffer, risks. Report immediately only for an owner-level blocker or when nothing is left. About 12 lines. Routine decisions, findings and rework are not reported; they are in PRs, the decision log and the changelog.
- **Why:** visible progress without interruption. **Default:** as stated. **Alternatives:** daily status (too noisy). **Change when:** the owner asks for more.

## 12. Pending-owner-review decisions
- **Rule:** the PO and the Architect decide each default or assumption and log it "decided, pending owner review". The list is passed to the owner as information when the next release is planned. Work does not wait for an answer; the owner may ask for a change at any time (a change is a new row). The team never writes "confirmed by owner".
- **Why:** the team must keep moving; the owner must stay able to reverse. **Default:** as stated. **Alternatives:** ask on each decision (stalls). **Change when:** reversal cost is high; mark that row an owner-level item.

## 13. Licence
- **Rule:** choose the licence with the owner. Add the notice file and record third-party licences. Keep a third-party file whose licence is unconfirmed out of git until confirmed.
- **Default:** none; decide with the owner on day 1. **Owner agreement for WatchYourList:** proprietary, all rights reserved, with a placeholder holder the owner replaces with the legal entity; nothing is redistributed until the entity is named. **Alternatives:** open source (another project of the owner is open source with pluggable adapters and optional providers). **Change when:** the owner decides otherwise.

## 14. Accessibility
- **Rule:** Testers run a role, name, keyboard and contrast pass for every story; a real assistive-technology audit (screen reader on desktop and phone) is an owner item arranged before the first public release and does not block the build.
- **Why:** agents have no real screen reader; the pass is limited and says so. **Default:** as stated. **Alternatives:** audit per release (cost). **Change when:** a public or regulated release is near, or the target is higher than AA.

## 15. Manual Testers in a browser, and no tests or CI in a repo
- **Rule:** Testers verify by hand on the running app in a browser (acceptance walk-through from the story, exploratory pass, light and dark, desktop and phone widths, keyboard, data states, console and network), screenshots as evidence, a results table in the PR. Limits are stated in every result (not a real screen reader, emulated phone is not a device).
- **Owner agreement (WatchYourList app repo only):** the repo's existing rule stands: no new automated tests and no CI; existing tests stay but are not run. This is a project-specific choice, not a general rule.
- **How to choose: Suggested default (not an owner agreement).** Pick **manual only** when the app is early and screens change daily, the repo already forbids tests and CI, or the owner wants no automation cost. Pick **automated tests plus CI** when screens stabilise, a regression has occurred more than once, several people merge into one repo, or a repo has contracts machines can check. Mixed is fine per repo: scripts that check documents and generated files stay even when the app has no tests. Record the choice per repo as a decision row and say it in each brief. For a project with tests and CI see `VARIANTS.md`.
- **Alternatives:** unit and end-to-end tests in the app (an architect plan proposed them; the plan was voided because the repo's rule stands). **Change when:** the repo's rule changes by decision.
- **Browser procedure:** `TEMPLATES/agent-prompts.md` (Tester).

## 16. Adaptability: ports, adapters, mock adapters
- **Rule:** no external system is a hard dependency. Each (market data, auth, notifications, payments, storage, AI provider...) sits behind a **port** with an adapter contract, a real adapter slot and a **mock adapter** that returns labelled synthetic data. Vendor names and SDKs never reach logic or UI. Adapters are selected by configuration (real, mock, off; unknown means off). Replacing mocks by real adapters is gated by data supply and licences, not engineering. The Architect owns the port catalogue and checks it in every architecture review. A new external dependency means a port, a contract file and a mock spec in the same PR.
- **Why:** build and demo without real data or accounts; vendor swaps stay local. **Default:** as stated. **Alternatives:** direct vendor calls with a later wrapper (costly to unpick). **Change when:** never for external systems; internal pure functions need no port.

## 17. Data rule
- **Rule (project-specific, owner-stated):** real adapters read stored values from the named store; if the data a feature needs is not stored, serve mock data labelled illustrative behind the same adapter; per field with per-value provenance (stored or mock); nothing is computed to fill a gap; nothing reads a vendor directly. Reading rows by key and date window, and comparing a stored value with a threshold, are reads; counts, percent changes, ratios, percentiles and ranking are calculations and wait until a worker stores them. A stored placeholder (for example zero-filled rows flagged incomplete) is not a value.
- **Example from WatchYourList:** stored values come from the N-drive DuckDB (delete or replace on copy); see the appendix.
- **Change when:** the project computes live; then define where calculation may happen and who owns it.

## 18. Researcher cadence
- **Rule:** the Researcher is read-only, holds exactly two ideas at a time, brainstorms them with the PO (and the Architect for feasibility), researches again only after both are resolved (accepted, rejected or parked), and proposes at most two ideas per calendar day. Otherwise idle. Each idea: problem, sourced evidence, proposed change, cost, risk; mix types; flag licensing, pricing and legal matters to the owner, never decide them. No repo edits until the PO accepts one.
- **Why:** steady improvement without noise or token burn. **Default:** as stated. **Alternatives:** continuous background research (cost, noise). **Change when:** the roadmap is thin and the owner wants more ideas; raise the daily cap by decision.

## 19. Ask the owner one question at a time
- **Rule:** when a decision is genuinely the owner's, ask ONE question with the question tool and 2 to 4 selectable answers, recommended first. Keep replies that carry a question short. Never bundle questions or bury one at the end of a status report.
- **Why:** the owner said questions got hidden behind long replies. **Default:** as stated. **Alternatives:** a list of questions at the end of a report (still used for non-blocking items in a release report). **Change when:** the tooling has no question tool; then one short message with numbered options.

## 20. Safety rules every change keeps
1. No push to main; branch, PR, merge by the coordinator after the three reviews, PO acceptance and checks.
2. Nothing public before its gate; later-release features are built behind a switch, off.
3. Never write "confirmed by owner", "accepted by counsel" or "verified" without the evidence; Verified and Not verified are written honestly in every changelog entry.
4. No legal advice; legal-pending wording stays a tagged key; a real lawyer closes each item.
5. No real credentials, accounts or personal data in any test.
6. A reviewer is never the author; one role cannot grant its own approval.
7. Never delete data, branches or history to make a check pass; never add to a check baseline to hide new drift.
8. No spend or new paid service without the owner.
9. Commit and PR attribution follows each repo's own rule.

## 21. Changing the agreement
Any role may propose a change in a PR; the PO decides, with the Architect's review where it touches technical rules; the change is a decision row. Reversal cost is low (documents only).

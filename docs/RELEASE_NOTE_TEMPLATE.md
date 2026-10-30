# Release note template (PO release plan V3, section 5)

Every release note, README and report header from P1 through M5 carries this sentence verbatim:

> mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads, Windows x64, CPython 3.12

## Label rules
1. Forbidden before the final real-data qualification release (RQ) passes: "real-data", "market data", "production", "validated against vendor", "Databento-qualified", "Linux parity" (write "Linux run as process check, not claimed"), any accuracy or latency number without the qualifier "synthetic workload", and "byte-identical" outside the 111 parity files.
2. The release label stays PRERELEASE (D7). D7's trigger is the RQ release.
3. Scanners stay shadow, ProductionAuthorized false (D6); proxy wording rules stand.
4. (From V3 section 3.) Performance numbers are labelled "synthetic workload, relative engineering budget" and print the B1-B12 budget beside the measurement. No real-chain performance claim before RQ.
5. A docs reviewer greps every doc for the forbidden list above as a release gate.
6. RQ wording, when earned: "qualified on recorded real data for symbols/sessions X, Windows x64 and Linux x64", never broader than what was pulled.
7. Every release PR updates docs/FEATURE_STATUS.md (the single live tracker of every planned feature): rows touched, status, release, PR numbers, evidence level, pending reasons, the summary counts and the gate state; the release note says so, and the docs reviewer checks the update as a release gate. A row is marked done only when the module and the passing fixture rows or tests are named; library modules not exposed on the wire are labelled so.

## Sections
1. Scope and version. 2. Label sentence (above). 3. What changed (bytes: bump, additive, frozen). 4. Gates and evidence (fixtures, independent reviewer, mutation proof). 5. Performance against B1-B12 (synthetic workload). 6. Pending design requests and their interim rulings. 7. Disclosed limits and flagged rows. 8. Owner items. 9. Feature status: the FEATURE_STATUS.md rows changed by this release.

# R26 supplemental independent regressions

These original synthetic fixtures add **20 cases and126 complete expected rows**: eight definition-partition cases/78rows and twelve selection-clock cases/48rows. These are regression cases, not20additional features or replacement definitions for the44native output IDs or44original scenario definitions. [EQ188](https://github.com/atulsrivas1/equity-features/issues/534) retains the frozen mathematics/boundary authority. Existing reference helpers, original full artifact and six normative files are unchanged.

| Fixture | Bytes | SHA256 of exact UTF-8 LF file |
| --- | ---: | --- |
| [definition-partitions.json](../../qualification/r26/supplements/definition-partitions.json) | 961763 | `9de68b13059510729d04d268dff9c099e1cec560e313284d93f75ed528449268` |
| [selection-clocks.json](../../qualification/r26/supplements/selection-clocks.json) | 519885 | `366b4043c2c3bfc7251f4a9dc9c92baca2ca09597f953658ba279e6a6945ffb8` |

Every case includes closed snapshot/request records and canonical input wires/domain hashes; literal hand projections; complete independent expected result records, canonical result wire and digest. Synthetic rights are explicitly bound inside the inputs. No market observations, private datasets or machine paths are included. Filenames in source-identity receipts are bare portable names.

## Definition partitions

Mathematics section5 partitions by contract/session/stream and semantic definition before ordering the adjacent-gap sequence. The definition tuple is underlying/currency/action/right/exact strike/exact multiplier/expiry. Reference IDs attest provenance and do not create different semantic definitions. Four cases change strike, right, multiplier or expiry independently. Further controls merge equivalent definitions with different reference IDs, group A/B/A interleaving before adjacency, and distinguish an unknown inside A from an unknown belonging only to B. Literal memberships, premium/count/contracts/span/venue values and coverage are checked. Known price2 against midpoint1 gives premium2 per quantity1/multiplier1; multiplier2 gives4; partial unknown coverage is4/5. The FLOW_CONTRACT97 cluster record and hash payload remain unchanged.

## Selection clocks

Six quote cases distinguish no removal, a removed latest quote, an irrelevant removed older quote, no survivor, a post-A removal and a cursor-hidden removal. Target price3/quantity1/multiplier100 has gross premium300. Surviving q1 midpoint2 gives buy300; q2 midpoint4 gives sell-300. A relevant cancellation known20 moves availability from15 to20; irrelevant/unadmitted removal does not. No survivor gives unknown premium300 and signed0 at20.

Six tick cases use pre-window100/99 and current100 with multiplier100. The admitted prefix gives buy10000 at15. A matching cancellation or exclusion known20 leaves equal-only history and unknown premium10000 at20. Removals in a different definition, session or contract/stream do not advance the target clock. F43 minimal context membership/deduplication/order/digest remains unchanged: a selection-cause clock does not insert cancellation records into the minimal context operand list. Full conservative input/dependency provenance remains separate from economic availability.

## Independence and executed evidence

Fixture author: `/root/r26_fixture_materialization_independent_review`, acting as supplemental author. Coordinator: `/root`. Independent emitted-artifact auditor: `/root/r26_native_io_independent_review`, distinct from the golden author. That auditor used a separate standard-library reducer, importing neither these generators/reference helpers nor production. It independently reconstructed every field of all126rows, including mathematics, units, signs/contexts, clocks, coverage, dependencies, diagnostics, cluster records and canonical hashes. The successful audit receipt SHA256 is `500951200ae37d1b1bac64d9a56efda5ebc019056319f8fc0a75741b237dd1d9`; audited reducer source SHA256 `f89c653222780c067356482578d5085afc98342cefc91158e8ce26bbd956533e`. Actual generation and audit used separate serialized coordinator grants and preserved original sources and fixtures.

The coordinator's recorded **Windows/Python3.12.10 source-development** run passed16contracts+57features unittest methods (73total, zero failures/errors/skips), the unchanged433original complete rows/19error witnesses and all126supplemental rows. Exact source-manifest SHA256: `8870587864ceff097ceb8d0d6cb284d9d6ccbbbc6a5533b9b2cb10c69a718b48`; isolated consumer source SHA256: `87a693852fcf7483a1975394423876ef30a4e18a650237a8296b4ad372341187`. This was an exact manifest-bound working-source run, not an installed artifact/platform qualification. It used one active job/inflight/I/O/backend slot and a logical256MiB reservation, without claiming RSS enforcement. These figures describe actual prior evidence; authoring the public CLI below did not rerun it.

## Portable regeneration

From the repository root, after coordinating resource use, select **new** output paths:

```text
python -I -B qualification/r26/supplements/generate_definition_partitions.py NEW_DEFINITION_OUTPUT.json
python -I -B qualification/r26/supplements/generate_selection_clocks.py NEW_CLOCK_OUTPUT.json
```

The public wrappers remove private coordinator lease/workspace dependencies and locate the pinned helpers relative to their own files. They use standard library and the reviewed independent reference namespace only. All case/construction functions are AST-identical to the approved private generators; only CLI location/resource-policy wiring and module descriptions differ. The caller/coordinator retains runtime admission responsibility. Output creation is exclusive, never overwriting existing evidence. Three helper pins and six normative source pins are checked before/after generation; UTF-8 universal-newline/LF framing preserves all other characters and the final newline. A private namespace receives the original supplemental algorithm; original modules/files are not modified. Narrow attributes keep these Python/JSON sources LF in Git.

Public generator source identities under UTF-8 LF framing are:

- `generate_definition_partitions.py`: `649e38e6a90f83bbfef9750e928592b9a6b7467c1ea6ee7864b2e2584fbab8fd`.
- `generate_selection_clocks.py`: `090474d6069fdfc399d4ba4e5b6195e22c6f3c63331f380fdb6bbed72cfa178a`.

These are public portable source identities, distinct from historical private CLI hashes. After fresh independent source review, both public commands were actually run serially on Windows CPython3.12.10 with `-I -B`. Their outputs exactly reproduced the two audited hashes, byte counts and20-case/126-row census in the table. Both contained children exited0, their process trees were empty and their leases released; generators, reference helpers and normative inputs were unchanged. This establishes Windows regeneration, not execution of the new installed conformance checker or a Linux regeneration claim. Corrected installable artifacts and actual installed-platform qualification remain pending.

## Installed supplemental conformance

Use the [public checker](../../qualification/r26/check_supplements.py) in a fresh process of an already qualified contracts/features or full flow environment. From the repository root:

```text
<qualified-python> -I -B qualification/r26/check_supplements.py --definition-fixture qualification/r26/supplements/definition-partitions.json --definition-fixture-sha256 9de68b13059510729d04d268dff9c099e1cec560e313284d93f75ed528449268 --clock-fixture qualification/r26/supplements/selection-clocks.json --clock-fixture-sha256 366b4043c2c3bfc7251f4a9dc9c92baca2ca09597f953658ba279e6a6945ffb8 --report NEW_REPORT.json
```

The checker strictly decodes inputs and compares all20 cases/126 complete rows, canonical payloads, record digests and wires against the externally pinned files. It records actual producer module identities and installed versions before/after. Caller-owned closed inventory, RECORD, origin and artifact admission must occur separately; this checker does not create an admitted cohort. It imports only the pure flow packages and rejects already-loaded I/O, worker or DuckDB modules, so any worker-based cohort verifier must run in a separate process. Source review approved checker SHA256 `5ab9839cba9585079dcf70b58ea3c66d8232742fee643ec784cc0a9f79031c00`; its installed execution remains pending at this source checkpoint.

This evidence does not qualify all source/history variants, corrected installed Windows/Linux cohorts, worker/storage/resource/browser gates, actual EQ153/EQ158 integration, EQ190 functionality, package publication or full R26 acceptance. Keep those release gates explicit.

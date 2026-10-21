# Pure option flow example

This example reads four original synthetic option executions, decodes the strict flow inputs and calls the installed `evaluate_flow` API. It prints the library's exact values, units, availability, status and reason for23 selected option-native outputs. `--canonical` writes the complete strict result envelope for byte comparison. It does not recompute feature formulas for display.

Use Python3.12 with an independently qualified installation of `option-flow-contracts==0.1.0a1` and `option-flow-features==0.1.0a1`. These two distributions form the pure calculation closure; no I/O/worker package, DuckDB, R25 runtime or flint is required by this example. The commands below assume an already prepared installation and do not install or publish anything:

```text
<installed-python> -I -B <absolute-path>/examples/r26/pure_flow_demo.py
<installed-python> -I -B <absolute-path>/examples/r26/pure_flow_demo.py --canonical
```

Use the actual installed interpreter path, with no PYTHONPATH. On Windows that can be an admitted environment's `Scripts/python.exe`; on Linux, `bin/python`. `-I` resolves package imports from that environment, while the input files are located beside this script. `-B` avoids writing bytecode. File reading and stdout presentation are confined to the example, outside the pure calculation packages. There is no network, provider, database, credential, scheduling or publication operation.

The literal input wires are unchanged copies of the independently fixed F01 mixed-multiplier scenario. Its binding declares `provenance_mode=synthetic` and rights reference `Original synthetic fixture; no market observations.` All identifiers, executions and prices are synthetic. The inputs contain no private observations, credentials or private evidence paths. The source scenario is defined in the [independent fixture cases](../../docs/r26/INDEPENDENT_FIXTURE_CASES.json), under the frozen [mathematics](../../docs/r26/MATHEMATICS.md) and [typed contracts](../../docs/r26/FLOW_CONTRACT.md).

| Execution | Contract/right | Event | Price | Quantity | Multiplier | Supplied side |
|---|---|---:|---:|---:|---:|---|
| a | A/call | 11 | 2 | 3 | 100 | buy |
| b | A/call | 12 | 1.5 | 2 | 100 | sell |
| c | B/put | 13 | 4 | 1 | 100 | buy |
| d | C/put | 14 | 2 | 1 | 50 | unknown |

The request selects group `all`, window `[10,20)`, knowledge cutoff20, and the supplied-side profile `option-observed-side1`. Currency `XTS` is a synthetic test denomination. Known-at facts and source cursors are explicit in the wires; the example does not read the wall clock or infer causal facts. Side-based values are flow proxies under that profile, not inferred investor intent.

The independently fixed hand expectations include premium1400, contracts7, trade count4, share-equivalent650, buy-proxy premium1000, sell-proxy premium300, unknown premium100, call premium900 and put premium500. The readable output displays these stored exact rationals as `1400/1`, `7/1`, etc.; no rounding or secondary arithmetic is performed. Full canonical output also includes every independently specified identity, evidence operand, diagnostic, sign witness and dependency for all23 rows, so checking only these headline numbers is insufficient for complete validation.

These are native flow examples. EQ190 cross-market outputs remain gated on accepted compatible equity producers and genuine integration; this example does not claim those outputs or full R26 acceptance. Source authoring is separate from executed proof. The coordinator must validate this exact example against the independent full F01 wire in a fresh admitted installed pure closure before recording an execution result. No test run or release/publication claim is made by adding these files.

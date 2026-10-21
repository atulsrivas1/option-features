# Calculation source candidate

`option-features==0.1.0a1` exposes `option_features.evaluate(snapshot, request)`.
It returns ordered frozen Results and owns all nine R25 feature producers plus
the five named foundation outputs. Source has been authored; implementation
review and actual numerical acceptance remain open. No tests/builds/installs,
oracle generation, backend imports, benchmarks or platform qualification ran
during source authoring under the original EQ142 reservation.

Only the frozen European scalar continuous-carry model and batch snapshots are
implemented here. Worker replay evaluates independent snapshots through this same
pure API. Unsupported profiles, unknown bounds, precision/export limits and
unqualified execution modes never count as fulfilled feature coverage. There are
no fetching, filesystem/database, scheduling, credential, wall-clock or metadata
reads in kernels. Supplied spot is a fact, so no unused equity dependency is added.

Contracts are independently packaged. Numerical dependencies are exact alpha
`option-feature-contracts==0.1.0a1` and `python-flint==0.9.0`. The module imports
without loading flint; actual nonterminal model arithmetic acquires one exclusive
numerical owner and lazily imports the backend. It restores precision/thread state
on success and failure, rejects reentrancy and uses native threads1. Foreign flint
context mutation while evaluation runs is outside the admitted profile. Terminal
symbolic paths and pure reference/supplied outputs need no backend import.

Forward certificates use original exact Decimal spot/strike and exact rational
clock time, binary64 facts as exact dyadics, fixed128/256/512/1024/2048-bit tiers,
and outward persisted Decimal intervals. Point values require a relative error
certificate against the persisted endpoints. IV discards a side only after strict
certified ordering and requires both enclosed price residual and bracket width.
Residual export is exact and bounded. Bounds/precision failures are explicit.
Source review of formulas is not independent numerical or native-artifact proof.

Tagged backend APIs inspected as source include
[arb conversion and outward endpoints](https://raw.githubusercontent.com/flintlib/python-flint/0.9.0/src/flint/types/arb.pyx)
and [precision/thread context](https://raw.githubusercontent.com/flintlib/python-flint/0.9.0/src/flint/flint_base/flint_context.pyx).
No native code was imported. Installed wheel identities, native notices/licenses,
actual conversion inclusion, tail error, context and platform behavior still need
executed evidence and independent review.

Authored unit probes cover hand-derived reference formulas, causal revisions,
quote-slot coverage, population breadth, signed-to-absolute supplied projection,
terminal endpoints without native import, analytical normal-symmetry interior
checks, exact IV boundaries and context restoration. They are unexecuted. The
ordinary binary64 erfc probe is complementary to the independent80/140-digit
oracle and cannot replace it.

The mandatory separate suite
`tests/qualification/test_independent_wire_fixtures.py` fails clearly if a qualified
independent fixture artifact or its separately recorded SHA256 is missing. It
requires wire-identical decimal economics/binary64 ratios, independent author and
review identities, all ten normative fixture families, full selected provenance
checks, meaningful nonzero-tail budgets and IV residual/width/root containment.
It does not fabricate expectations or silently skip absent evidence. The current
documentary oracle examples have not been instantiated as these wire artifacts;
they cannot satisfy this gate merely by renaming their metadata.

After execution admission, use separately recorded installed artifacts and source
receipts to run contracts tests, feature unit probes and the qualification suite
in fresh Python3.12 interpreters against installed wheels. Qualification variables
are `R25_INDEPENDENT_WIRE_FIXTURES` and
`R25_INDEPENDENT_WIRE_FIXTURES_SHA256`. A purported artifact's metadata alone does
not prove independent review; the coordinator must retain the real review receipt.
Both supported platforms need their own evidence. Complete direct/worker/stored
parity, artifact/licensing inventory, resource/cancellation proof and actual stored
browser demo remain release gates.

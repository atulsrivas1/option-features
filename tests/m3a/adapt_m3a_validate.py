"""S09 adapter: maps author4 structural, aux and lane rows and the author1 frame-request rows (COV-35..37,
D25-V1..V7) to the `option_features.m3a_validate` API. It only reshapes inputs; expectations come from the rows.

Store entries (history append and load, snapshot load, text load) go through the M2 store unchanged (R-70); the
history_load rows carry a per-record lane, which the M2 text form cannot hold, so they are replayed record-major
(R-148: each record is checked at its append, in stream order). The ring depth `k` of a row is clamped to the store
cap `flowstore.MAX_K`: these rows hold at most four records, so no code depends on the depth.

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12.
"""
from option_features import flowstore
from option_features import m3a_validate as V
from option_features.chainiv import ChainContract
from option_features.flowgrid import Calendar

CONTRACT_FIELDS = ChainContract._fields


def contracts_of(raw):
    """Row contract dicts as M1 `ChainContract` records (missing optional fields take the M1 defaults)."""
    return [ChainContract(**{f: c[f] for f in CONTRACT_FIELDS if f in c}) for c in raw]


def request(inputs, params, output_id=None):
    """First structural code of a request row (None when valid)."""
    p = dict(params)
    oid = output_id or p.pop("output_id", None) or "M3A-0"
    p.pop("output_id", None)
    return V.validate_request(oid, contracts_of(inputs["contracts"]), inputs["spot"], inputs["rate"],
                              inputs["dividend_yield"], inputs["cutoff_ns"], p)


def calendar_of(rows):
    return Calendar([(s, m) for s, m in rows])


def view_read(inputs, params):
    p = params
    return V.validate_view_read(calendar_of(inputs["calendar"]), inputs["as_of"], inputs["form"],
                                p.get("min_sessions"), p.get("max_sessions"), x=p.get("x"), minute=p.get("minute"),
                                series_id=inputs["series_id"], delta_convention=p.get("delta_convention", "spot"))


def _store(inputs):
    return flowstore.HistoryStore(calendar_of(inputs["calendar"]), k=min(inputs["k"], flowstore.MAX_K))


def _append(store, op):
    store.append(op["series_id"], op["metric"], op["window_s"], op["session_id"], op["grid"], total=op.get("total"),
                 complete=op.get("complete", True), grid_idx=op.get("grid_idx"), lane=op.get("lane", "stock"))


def history_ops(inputs):
    """(code, op_index) of the first failing record of an append or record-major load stream; (None, None)."""
    store = _store(inputs)
    for i, op in enumerate(inputs["ops"]):
        _, code = V.store_call(_append, store, op)
        if code is not None:
            return code, i
    return None, None


def snapshot_load(inputs):
    cal = calendar_of(inputs["calendar"])
    _, code = V.store_call(flowstore.HistoryStore.from_snapshot, bytes.fromhex(inputs["snapshot_hex"]), cal,
                           k=min(inputs["k"], flowstore.MAX_K))
    return code


def text_load(inputs):
    cal = calendar_of(inputs["calendar"])
    _, code = V.store_call(flowstore.HistoryStore.load, inputs["text"], cal, k=min(inputs["k"], flowstore.MAX_K))
    return code

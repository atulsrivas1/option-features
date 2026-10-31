"""S07 adapter: maps the author3 V4, V7 and V10 rows to the `option_features.surface_change` API. It only reshapes
inputs; expectations come from the rows.

Per row: the S05 frame is built from the row chain (`surfaceframe.surface_frame`, stats dict receives the unrounded
floats), the stored priors become a real S02 `HistoryStore` (scalar series, one record per prior session), and the
request dict gets `prior` / `priors` (readings with their times and conventions, for the structural checks of
position 17).

Two stand-ins the real pipeline lacks today (decision file 2026-10-31-m3a-s07.md, open question 1):
  * `floats["expiries"][days]["label"]`: the model label of the expiry's ATM legs. S05 keeps it private
    (`_Expiry.atm_label`); the stand-in re-runs `surfaceframe._assemble` (private, test-only) until an S05 patch
    exposes it, the same way the S10 tests built `stats["floats"]` before S05 exposed it.
  * fixture session ids: the fixtures name the prior sessions S-01 (most recent) .. S-05, which sort the wrong way
    for the ascending-id M2 calendar; the adapter maps them to ascending dates and maps result ids back.

Label: mock-data qualification only: passed on independently authored synthetic fixtures and synthetic workloads,
Windows x64, CPython 3.12.
"""
from option_features import surface_change as SC
from option_features import surfaceframe as SF
from option_features.chainiv import ChainContract
from option_features.flowgrid import Calendar
from option_features.flowstore import HistoryStore

FRAME_KEYS = ("tenors", "delta_target", "min_strikes", "min_coverage", "stale_limit_ns", "feed_delay_tag", "mode",
              "lane", "evaluation_ns")
TODAY = "2026-02-01"


def contracts_of(raw):
    return [ChainContract(c["contract_id"], c["expiry_days"], c["right"], c["strike"], c["bid"], c["ask"],
                          c["event_ns"], c["known_at_ns"], c["style"], c["condition"]) for c in raw]


def frame_params(row):
    """Request keys the frame reads; V4 to V7 do not take `delta_convention` (R-149): V10 only."""
    req = row["inputs"]["request"]
    p = {k: req[k] for k in FRAME_KEYS if k in req}
    if row["family"] == "V10" and "delta_convention" in req:
        p["delta_convention"] = req["delta_convention"]
    return p


def with_labels(floats, contracts, ch, p):
    """Stand-in for the S05 patch: floats["expiries"][days]["label"] (ATM-leg model label of an available expiry)."""
    exps = SF._assemble(contracts, ch["spot"], ch["rate"], ch["dividend_yield"], ch["cutoff_ns"], SF._params(p), None,
                        None)[0]
    for e in exps:
        if e.status == "available":
            floats["expiries"][str(e.days)]["label"] = e.atm_label
    return floats


def build_frame(row):
    """(frame Result, floats) of the row chain."""
    ch = row["inputs"]["chain"]
    contracts = contracts_of(ch["contracts"])
    p = frame_params(row)
    stats = {}
    res = SF.surface_frame(contracts, ch["spot"], ch["rate"], ch["dividend_yield"], ch["cutoff_ns"], p, stats=stats)
    floats = stats.get("floats")
    if floats is not None:
        with_labels(floats, contracts, ch, p)
    return res, floats


def session_map(priors_store):
    """fixture id -> ascending calendar date (S-01 is the most recent prior)."""
    ids = sorted({p["session_id"] for p in priors_store}, reverse=True)       # oldest first
    return {sid: "2026-01-%02d" % (i + 1) for i, sid in enumerate(ids)}


def build_store(priors_store, series_id, lane):
    """(store, fixture-id map) holding the stored priors as scalar records of the real S02 store."""
    smap = session_map(priors_store)
    cal = Calendar([(d, 390) for d in sorted(smap.values())] + [(TODAY, 390)])
    store = HistoryStore(cal, k=20)
    metric = series_id.rsplit("/", 1)[1]
    for pr in sorted(priors_store, key=lambda r: smap[r["session_id"]]):
        conv = pr.get("delta_convention")
        store.append(series_id, metric, 0, smap[pr["session_id"]], [], total=pr["value_int"], lane=lane,
                     delta_convention=conv if conv in ("spot", "forward") else None)
    return store, smap


def request(row, smap=None):
    """The S07 request dict: the row request plus the supplied readings (position 17 checks their times)."""
    inp = row["inputs"]
    p = dict(inp["request"])
    if inp["prior"] is not None:
        p["prior"] = dict(inp["prior"])
    if inp["priors_store"]:
        p["priors"] = [{k: v for k, v in (("session_id", (smap or {}).get(r["session_id"], r["session_id"])),
                                         ("time_ns", r["time_ns"]), ("delta_convention", r.get("delta_convention")))
                        if v is not None} for r in inp["priors_store"]]
    return p


def run_row(row):
    """(Result, smap): smap maps calendar dates back to the fixture session ids (identity for V4)."""
    inp = row["inputs"]
    frame, floats = build_frame(row)
    cutoff = inp["chain"]["cutoff_ns"]
    fam = row["family"]
    if fam == "V4":
        return SC.iv_change(frame, floats, cutoff, request(row)), {}
    lane = inp["request"].get("lane", "stock")
    store, smap = build_store(inp["priors_store"] or [], inp["series_id"], lane)
    p = request(row, smap)
    fn = SC.gap_change if fam == "V7" else SC.skew_change
    res = fn(frame, floats, cutoff, p, store, inp["series_id"], TODAY)
    return res, {v: k for k, v in smap.items()}

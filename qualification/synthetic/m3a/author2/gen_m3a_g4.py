"""G4 history generators (SYNTHETIC): planted rank positions, ties, constant history, missing and incomplete days,
calendar gaps, half-day sessions, minute grids with decoy neighbours, look-ahead and today records, lane mismatch.
Library used by gen_m3a_V1/V3/V9/history/units. Running it writes m3a_g4_histories.json (fingerprints of named
histories) and nothing else. Stdlib only, seeded, deterministic."""
import os
import random

import m3a_common as C
import m3a_ref as R

HOL = ("2024-01-15", "2024-02-19", "2024-03-29", "2024-05-27", "2024-06-19", "2024-07-04", "2024-09-02")
CAL_SCALAR = C.make_calendar(300, 390, holidays=HOL)
REF_SCALAR = C.cal_ref(CAL_SCALAR)
# minute calendar: 30-minute sessions, every 17th session a half-day of 12 minutes (indexes 16, 33, ...)
HALF = {i: 12 for i in range(16, 300, 17)}
CAL_MIN = C.make_calendar(300, 30, half=HALF, holidays=HOL)
REF_MIN = C.cal_ref(CAL_MIN)
CALS = {REF_SCALAR: CAL_SCALAR, REF_MIN: CAL_MIN}
HEAD = 8


def rng_for(tag):
    return random.Random("%d:%s" % (C.SEED, tag))


def plant(rng, n, ge, le, lo=2_000_000, hi=95_000_000, xlo=30_000_000, xhi=60_000_000):
    """n integer history values and x (10^-8 units) with count(h>=x)=ge and count(h<=x)=le (ties t=ge+le-n)."""
    t = ge + le - n
    assert 0 <= t <= min(ge, le), (n, ge, le)
    up, dn = ge - t, le - t
    x = rng.randrange(xlo, xhi)
    below = rng.sample(range(lo, x), dn) if dn else []
    above = rng.sample(range(x + 1, hi), up) if up else []
    vals = below + [x] * t + above
    rng.shuffle(vals)
    return x, vals


def const_hist(rng, n, v=None):
    v = rng.randrange(10_000_000, 80_000_000) if v is None else v
    return v, [v] * n


def _slots(rng, n_use, inc, miss, cur):
    roles = ["u"] * n_use + ["i"] * inc + ["m"] * miss
    rng.shuffle(roles)
    start = cur - len(roles)
    assert start >= 0
    return [(start + k, roles[k]) for k in range(len(roles))]


def scalar_records(rng, vals, x, cur, inc=0, miss=0, lookahead=(), today=None):
    """[[idx, units, complete]] for the usable values plus incomplete decoys, missing days, a look-ahead tail and today."""
    recs, k = [], 0
    for idx, role in _slots(rng, len(vals), inc, miss, cur):
        if role == "u":
            recs.append([idx, vals[k], 1])
            k += 1
        elif role == "i":
            recs.append([idx, x + 1000 if idx % 2 else x - 1000, 0])
    if today is not None:
        recs.append([cur, today[0], today[1]])
    for j, v in enumerate(lookahead):
        recs.append([cur + 1 + j, v, 1])
    assert len(recs) <= 252
    return recs


def grid_gs(rng, length, m, planted, x, base_lo=2_000_000, base_hi=95_000_000):
    """Dense minute grid: column m planted, neighbours m-1 and m+1 decoys on each side of x, other minutes random."""
    over = []
    if m is not None and m < length:
        over.append([m, planted])
        if m - 1 >= 0:
            over.append([m - 1, x + 1000])
        if m + 1 < length:
            over.append([m + 1, x - 1000])
    for i in range(0, length, 5):  # a few more decoys
        if m is None or abs(i - m) > 1:
            over.append([i, rng.randrange(base_lo, base_hi)])
    d = {}
    for i, v in over:
        d[i] = v
    return {"base": rng.randrange(base_lo, base_hi), "over": sorted([i, v] for i, v in d.items()), "len": length}


def minute_records(rng, vals, x, m, cur, inc=0, miss=0, cal=CAL_MIN, lookahead=(), today=None):
    """Window walked backward from cur: half-day sessions shorter than m+1 are skipped slots; roles shuffled over the rest."""
    roles = ["u"] * len(vals) + ["i"] * inc + ["m"] * miss
    rng.shuffle(roles)
    take = []
    idx = cur - 1
    while roles:
        if idx < 0:
            raise ValueError("calendar too short")
        take.append((idx, "h" if m >= cal[idx][1] else roles.pop()))
        idx -= 1
    take.reverse()
    k, recs = 0, []
    for idx, role in take:
        L = cal[idx][1]
        if role == "h":
            recs.append([idx, grid_gs(rng, L, None, 0, x), 1])
        elif role == "u":
            recs.append([idx, grid_gs(rng, L, m, vals[k], x), 1])
            k += 1
        elif role == "i":
            recs.append([idx, grid_gs(rng, L, m, x + 1000 if idx % 2 else x - 1000, x), 0])
    if today is not None:
        recs.append([cur, grid_gs(rng, cal[cur][1], m, today[0], x), today[1]])
    for j, v in enumerate(lookahead):
        recs.append([cur + 1 + j, grid_gs(rng, cal[cur + 1 + j][1], m, v, x), 1])
    assert len(recs) <= 252
    return recs


def strip(e):
    e = dict(e)
    e.pop("_all_reasons", None)
    return e


def finish(row, cals=CALS, force_pending=None, alt=None):
    """Attach the oracle expectation; mark PENDING-RULING when the D3 reading or the D4 gate order changes the answer."""
    pend = force_pending
    alts = list(alt or [])
    e = R.evaluate(row, cals)
    e_cal = R.evaluate(row, cals, reading="cal")
    key = lambda d: (d["status"], d["reason"], d["code"], d["value"], d["fired"])
    if key(e) != key(e_cal):
        pend = pend or "PENDING-RULING:D3"
        alts.append({"reading": "calendar window of max_sessions", "expected": strip(e_cal)})
    reasons = e.get("_all_reasons", [])
    if len(reasons) > 1:
        pend = pend or "PENDING-RULING:D4"
        for other in reasons[1:]:
            alts.append({"reading": "gate order: %s first" % other, "expected": {"status": "unavailable", "reason": other, "code": None, "value": None, "fired": None}})
    row["expected"] = strip(e)
    if e["status"] == "available":
        v = e["value"]
        auto = "n=%s usable prior values, rank_le=%s, upper_share=%s, X=%s -> fired=%s" % (
            v["n"], v["rank_le"], v["upper_share"], e["params"]["x"], e["fired"])
    else:
        auto = "status=%s reason=%s code=%s" % (e["status"], e["reason"], e["code"])
    row["derivation"] = (row["derivation"] + "; " if row["derivation"] else "") + auto
    row["pending"] = pend or "RULED"
    if alts:
        row["alt_expected"] = alts
    return row


def base_row(rid, family, oid, cal_ref, series, ring_lane, lane, sess_id, complete, tag, now, params, records, design_ref,
             rules, tags, derivation, model_label=C.EXACT, k=252, delayed=False, cutoff=None, **extra):
    so = C.open_ns(sess_id)
    ev = cutoff if cutoff is not None else so + 3 * 3600 * C.NS
    row = {"id": rid, "family": family, "output_id": oid, "design_ref": design_ref, "ruling": rules, "tags": sorted(tags),
           "derivation": derivation,
           "inputs": {"calendar_ref": cal_ref, "series": series, "lane": lane, "ring_lane": ring_lane, "store_k": k,
                      "records": records, "session": {"session_id": sess_id, "complete": complete,
                                                      "feed_delay_tag": "delayed" if delayed else "live"},
                      "cutoff_ns": ev, "evaluation_ns": ev, "now": now, "model_label": model_label},
           "params": params}
    row["inputs"].update(extra)
    return row


def pct_row(rid, family, oid, rng, ge, le, n, cur=None, inc=0, miss=0, X=None, tail=None, mode=None, mins=None, maxs=None,
            const=False, complete=True, delayed=False, lane="stock", ring_lane="stock", now_unavail=None, lookahead=(),
            today=None, rules=("R-45", "R-50"), tags=(), derivation="", model_label=C.EXACT, params_extra=None, now_units=None,
            x_float=None, put_call=None, force_pending=None, x_obj="unset", extra_params=None, session_in_cal=True,
            skew=False, no_finish=False, plain_params=None, prefix=(), vals_override=None, conv=None, records_conv=None):
    """History with planted ranks. skew=True plants signed values (V9)."""
    metric = R.OUT[oid]
    if oid == "M3A-8" and conv == "forward":
        metric = "skew25_fwd"
    lo, hi, xlo, xhi = (-30_000_000, 60_000_000, -8_000_000, 12_000_000) if skew else (2_000_000, 95_000_000, 30_000_000, 60_000_000)
    if vals_override is not None:
        x, vals = now_units, list(vals_override)
    elif const:
        x, vals = const_hist(rng, n)
        x = vals[0] if now_units is None else now_units
    else:
        x, vals = plant(rng, n, ge, le, lo, hi, xlo, xhi)
    vals = list(prefix) + vals
    if now_units is not None:
        x = now_units
    n = len(vals)
    cur = cur if cur is not None else HEAD + n + inc + miss + 3
    recs = scalar_records(rng, vals, x, cur, inc, miss, lookahead, today)
    if now_unavail:
        now = {"unavailable": now_unavail}
    elif skew:
        call = rng.randrange(15_000_000, 40_000_000)
        pu, ca = (call + x) / 1e8, call / 1e8
        assert C.r8(pu - ca) == x, (rid, x)
        now = {"put25_iv": pu, "call25_iv": ca}
    else:
        f = x / 1e8
        assert C.r8(f) == x
        now = {"float": f}
    if put_call:
        now = put_call
    if x_float is not None:
        now = {"float": x_float}
    sid = CAL_SCALAR[cur][0] if session_in_cal else "2099-01-05"
    params = dict(plain_params) if plain_params is not None else {}
    if plain_params is None:
        for k_, v in (("X", X), ("tail", tail), ("mode", mode), ("min_sessions", mins), ("max_sessions", maxs)):
            if v is not None:
                params[k_] = v
    if x_obj != "unset":
        params["X"] = x_obj
    if extra_params:
        params.update(extra_params)
    if conv is not None and conv != "__omit__":
        params["delta_convention"] = conv
    row = base_row(rid, family, oid, REF_SCALAR, {"series_id": "SYN1/%s/%s" % (lane, metric), "metric": metric, "window_s": 0}, ring_lane, lane,
                   sid, complete, None, now, params, recs, "volatility-radar.md V1/V9; matrix M3A-1/M3A-8", list(rules), tags,
                   derivation, model_label=model_label, delayed=delayed)
    if records_conv is not None:
        row["inputs"]["records_convention"] = records_conv
    return row if no_finish else finish(row, force_pending=force_pending)


def v3_row(rid, rng, ge, le, n, m, cur=None, inc=0, miss=0, X=None, mins=None, maxs=None, const=False, delayed=False,
           lane="stock", ring_lane="stock", now_unavail=None, lookahead=(), today=None, rules=("R-43", "R-45", "R-55"),
           tags=(), derivation="", extra_params=None, force_pending=None, now_units=None, x_obj="unset", minute_param="unset", iv_form="30d", series_metric=None):
    if const:
        _, vals = const_hist(rng, n)
        x = now_units if now_units is not None else vals[0]
    else:
        x, vals = plant(rng, n, ge, le)
    if now_units is not None:
        x = now_units
    cur = cur if cur is not None else 120
    mb = m if isinstance(m, int) and not isinstance(m, bool) and 0 <= m < 30 else 5
    recs = minute_records(rng, vals, x, mb, cur, inc, miss,
                          lookahead=lookahead, today=today)
    now = {"unavailable": now_unavail} if now_unavail else {"float": x / 1e8}
    params = {"minute": m if minute_param == "unset" else minute_param}
    if iv_form != "__omit__":
        params["iv_form"] = iv_form
    metric = series_metric or ("iv30" if iv_form == "30d" else "atm_iv")
    for k_, v in (("X", X), ("min_sessions", mins), ("max_sessions", maxs)):
        if v is not None:
            params[k_] = v
    if x_obj != "unset":
        params["X"] = x_obj
    if extra_params:
        params.update(extra_params)
    row = base_row(rid, "V3", "M3A-2", REF_MIN, {"series_id": "SYN1/%s/%s" % (lane, metric), "metric": metric, "window_s": 0}, ring_lane, lane,
                   CAL_MIN[cur][0], False, None, now, params, recs, "volatility-radar.md V3; matrix M3A-2", list(rules), tags,
                   derivation, delayed=delayed)
    return finish(row, force_pending=force_pending)


def header(family, extra=None):
    h = {"family": family, "format": "compact v1: rows carry records [idx, value, complete] indexing the calendar; "
         "minute grids as {base, over, len}", "calendars": {REF_SCALAR: CAL_SCALAR, REF_MIN: CAL_MIN}}
    h["calendars"] = {k: v for k, v in h["calendars"].items()}
    if extra:
        h.update(extra)
    return h


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = {}
    rng = rng_for("g4-catalogue")
    for name, (n, ge, le) in {"n20_top1": (20, 1, 20), "n21_top1": (21, 1, 21), "n252_top12": (252, 12, 241),
                              "n252_ties3": (252, 3, 252), "n100_mid": (100, 50, 51), "n252_bottom12": (252, 241, 12)}.items():
        x, vals = plant(rng, n, ge, le)
        out[name] = {"n": n, "x": x, "sha256": C.sha(C.canon([x, vals]))}
    out["const30"] = {"n": 30, "sha256": C.sha(C.canon(const_hist(rng, 30)))}
    out["calendar_scalar_sha256"] = C.sha(C.canon(CAL_SCALAR))
    out["calendar_minute_sha256"] = C.sha(C.canon(CAL_MIN))
    C.write_dataset(os.path.join(here, "m3a_g4_histories.json"), {"family": "G4", "note": "fingerprints of the named planted histories"},
                    [{"id": k, "value": v} for k, v in sorted(out.items())])


if __name__ == "__main__":
    main()

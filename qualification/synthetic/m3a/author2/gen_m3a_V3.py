"""Generator for family V3 (M3A-2): 30-day IV at grid minute m against the same minute of earlier sessions. SYNTHETIC.
Calendar: 30-minute sessions, every 17th session (indexes 16, 33, ...) a half-day of 12 minutes."""
import copy
import os

import gen_m3a_g4 as G
import m3a_common as C
import m3a_ref as R

FAM = "V3"
RB = ("R-43", "R-45", "R-50", "R-81")


def build():
    rows = []

    def V(n_id, **kw):
        rid = "M3A-V3-%03d" % n_id
        kw.setdefault("rules", RB)
        if "ties" not in kw.get("tags", ()) and "n" in kw and "ge" in kw:
            kw["le"] = kw["n"] - kw["ge"]
        kw.setdefault("le", 0)
        kw.setdefault("ge", 0)
        kw.setdefault("n", 0)
        rows.append(G.v3_row(rid, G.rng_for(rid), **kw))

    # A. 252 look-back at a minute every session has (m < 12), boundaries of the top-X rule
    V(1, ge=12, n=252, m=10, cur=270, X=5, mins=20, maxs=252, tags=["rank", "top", "boundary", "n252"], derivation="12/252 <= 1/20")
    V(2, ge=13, n=252, m=10, cur=270, X=5, tags=["rank", "top", "boundary", "n252"], derivation="13/252 > 1/20")
    V(3, ge=126, n=252, m=0, cur=270, X=50, tags=["rank", "top", "exact_boundary", "n252", "minute_first"], derivation="126/252 == 1/2 fires; minute 0")
    V(4, ge=2, n=252, m=10, cur=270, X=1, tags=["rank", "top", "boundary", "n252"], derivation="2/252 <= 1/100")
    V(5, ge=3, n=252, m=10, cur=270, X=1, tags=["rank", "top", "boundary", "n252"], derivation="3/252 > 1/100")
    V(6, ge=15, n=252, m=11, cur=270, X=6, tags=["rank", "top", "boundary", "n252"], derivation="15/252 <= 6/100; minute 11 exists in a half-day")
    V(7, ge=16, n=252, m=11, cur=270, X=6, tags=["rank", "top", "boundary", "n252"], derivation="16/252 > 6/100")
    V(8, ge=5, le=98, n=100, m=10, cur=130, X=5, tags=["ties", "top", "exact_boundary"], derivation="2 above plus 3 equal = 5/100 fires")
    V(9, ge=6, le=97, n=100, m=10, cur=130, X=5, tags=["ties", "top", "boundary"], derivation="3 above plus 3 equal = 6/100 no")
    V(10, ge=3, le=60, n=60, m=29, cur=130, X=5, tags=["ties", "top", "ties_top", "minute_last"], derivation="x equals the maximum, 3 copies; last grid minute 29")
    # B. sizes and defaults
    V(11, ge=1, n=20, m=10, cur=130, tags=["n20", "exact_boundary", "defaults"], extra_params=None, derivation="defaults X 5, min 20, max 252: 1/20")
    V(12, ge=1, n=21, m=10, cur=130, X=5, tags=["n21"], derivation="1/21 <= 1/20")
    V(13, ge=1, n=19, m=10, cur=130, X=5, tags=["n19", "insufficient"], rules=("R-44", "R-47"), derivation="19 < 20")
    V(14, ge=3, n=60, m=10, cur=140, X=5, maxs=30, tags=["cap", "max_sessions"], rules=RB + ("R-44",), derivation="60 stored, only the 30 most recent usable sessions are read")
    V(15, ge=1, n=12, m=10, cur=130, X=5, mins=10, tags=["min_sessions_param"], derivation="min_sessions 10 with 12 available")
    # C. half-day sessions by minute index (R-55), missing and incomplete sessions
    V(16, ge=2, n=40, m=14, cur=130, X=5, tags=["half_day", "skipped"], rules=RB + ("R-55",), derivation="sessions with 12 minutes have no minute 14: skipped, not substituted; 40 usable")
    V(17, ge=2, n=40, m=11, cur=130, X=5, tags=["half_day", "last_minute_of_halfday"], rules=RB + ("R-55",), derivation="minute 11 is the last minute of a half-day: those sessions are usable")
    V(18, ge=2, n=40, m=12, cur=130, X=5, tags=["half_day", "first_missing_minute"], rules=RB + ("R-55",), derivation="minute 12 is the first minute a half-day lacks: skipped")
    V(19, ge=1, n=20, m=14, cur=130, X=5, tags=["half_day", "n20", "exact_boundary"], rules=RB + ("R-55",), derivation="exactly 20 usable besides the skipped half-days")
    V(20, ge=1, n=19, m=14, cur=130, X=5, tags=["half_day", "n19", "insufficient"], rules=("R-55", "R-47"), derivation="19 usable plus skipped half-days: insufficient_history")
    V(21, ge=2, n=24, miss=6, m=5, cur=130, X=5, tags=["missing_sessions", "r51"], rules=RB + ("R-51",), derivation="6 calendar sessions without a record are skipped")
    V(22, ge=2, n=22, inc=4, m=5, cur=130, X=5, tags=["incomplete_day", "r47"], rules=RB + ("R-47",), derivation="4 incomplete sessions skipped")
    V(23, ge=1, n=19, inc=3, m=5, cur=130, X=5, tags=["incomplete_day", "insufficient"], rules=("R-47",), derivation="19 complete plus 3 incomplete: insufficient")
    V(24, ge=2, n=40, m=7, cur=130, X=5, lookahead=(96_100_000, 96_200_000), today=(96_300_000, 0), tags=["today_excluded", "lookahead", "alignment"],
      rules=RB + ("R-47",), derivation="today and later sessions never read; neighbours of minute 7 are decoys on both sides of x")
    V(25, ge=2, n=40, m=3, cur=130, X=5, tags=["alignment"], rules=RB, derivation="neighbouring minutes 2 and 4 carry values on each side of x: an off-by-one alignment changes the share")
    # D. zero range at the minute
    V(26, n=30, const=True, m=6, cur=130, X=5, tags=["zero_range"], rules=("R-46",), derivation="column at minute 6 constant, other minutes vary: zero_range_history")
    V(27, n=19, const=True, m=6, cur=130, X=5, tags=["zero_range", "insufficient", "gate_order"], rules=("R-46", "R-47"), derivation="two conditions: 19 constant")
    # E. minute range and types (positions 10, 16 of the request list)
    V(28, ge=2, n=40, m=30, cur=130, X=5, tags=["structural", "minute_out_of_range"], rules=("R-54",), derivation="minute 30 on a 30-minute session")
    V(29, ge=2, n=40, m=-1, cur=130, X=5, tags=["structural", "minute_out_of_range"], rules=("R-54",), derivation="minute -1")
    V(30, ge=2, n=40, m=12, cur=135, X=5, tags=["structural", "minute_out_of_range", "half_day_current"], rules=("R-54", "R-55"), derivation="current session 135 is a half-day of 12 minutes: minute 12 outside its grid")
    V(31, ge=2, n=40, m=11, cur=135, X=5, tags=["half_day_current"], rules=("R-54", "R-55"), derivation="current half-day, last minute 11 valid; usable column excludes sessions without minute 11 (none)")
    V(32, ge=2, n=40, m=True, cur=130, X=5, minute_param=True, tags=["structural", "type_first", "minute"], rules=("R-54", "R-67"), derivation="bool minute: malformed_type")
    V(33, ge=2, n=40, m=5, cur=130, X=5, minute_param=5.0, tags=["structural", "type_first", "minute"], rules=("R-54", "R-67"), derivation="float minute: malformed_type")
    V(34, ge=2, n=40, m=5, cur=130, X=5, minute_param=None, tags=["structural", "type_first", "minute"], rules=("R-54", "R-67"), derivation="None minute: malformed_type")
    V(35, ge=2, n=40, m=10, cur=130, X=101, tags=["structural", "threshold"], rules=("R-72",), derivation="X 101")
    V(36, ge=2, n=40, m=40, cur=130, X=101, tags=["structural", "precedence_pair"], rules=("R-66",), derivation="X 101 (position 15) and minute 40 (position 16): threshold_out_of_range first")
    V(37, ge=2, n=40, m=40, cur=130, X=5, delayed=True, tags=["structural", "precedence_pair", "delayed"], rules=("R-66", "R-58"), derivation="minute 40 (16) and delayed (18): minute_out_of_range first")
    V(38, ge=2, n=40, m=10, cur=130, X=5, delayed=True, tags=["delayed"], rules=("R-58",), derivation="V3 is live only: delayed_feed_tag")
    V(39, ge=2, n=40, m=10, cur=130, X=5.5, tags=["structural", "type_first"], rules=("R-67",), derivation="float X: malformed_type")
    V(40, ge=1, n=40, m=10, cur=130, x_obj=C.tag_fraction("5/2"), tags=["tagged_fraction", "exact_boundary"], rules=RB + ("R-65",), derivation="X=5/2: 1/40 fires")
    V(41, ge=2, n=40, m=10, cur=130, X=5, mins=0, tags=["structural", "min_sessions"], rules=("R-72",), derivation="min_sessions 0: malformed_type")
    # F. upstream, lane
    V(42, ge=2, n=40, m=10, cur=130, X=5, now_unavail="no_bracketing_expiry", tags=["upstream_reason"], rules=("R-81",), derivation="iv30 at the minute unavailable: reason propagates")
    V(43, ge=1, n=10, m=10, cur=130, X=5, now_unavail="no_bracketing_expiry", tags=["upstream_reason", "gate_order", "insufficient"], rules=("R-81",), derivation="two conditions: unavailable and 10 sessions")
    V(44, ge=2, n=40, m=10, cur=130, X=5, ring_lane="etf_index", tags=["lane", "lane_read"], rules=("R-73",), force_pending="PENDING-RULING:D5", derivation="ring lane etf_index under request lane stock")
    rows[-1]["alt_expected"] = [{"reading": "R-73 text: history lane mismatch is lane_mismatch",
                                  "expected": {"status": "invalid_input", "reason": None, "code": "lane_mismatch", "value": None, "fired": None}}]
    # G. stored grid shorter than the calendar minutes (D6): skipped here, zero-padded under the M2 read rule
    r = G.v3_row("M3A-V3-045", G.rng_for("M3A-V3-045"), ge=2, le=38, n=40, m=8, cur=130, X=5, tags=["short_grid", "d6"], rules=("R-43", "R-55"),
                 derivation="10 stored grids are shorter than the session minutes (5 values): no minute 8 in them")
    short = [x for x in r["inputs"]["records"] if x[2] == 1][-10:]
    for x in short:
        gs = x[1]
        gs["len"] = 5
        gs["over"] = [o for o in gs["over"] if o[0] < 5]
    G.finish(r, force_pending="PENDING-RULING:D6")
    padded = copy.deepcopy(r)
    for x in padded["inputs"]["records"]:
        if x[2] == 1 and x[1]["len"] == 5:
            full = C.expand_gs(x[1]) + [0] * (G.CAL_MIN[x[0]][1] - 5)
            x[1] = {"base": 0, "over": [[i, v] for i, v in enumerate(full) if v != 0], "len": len(full)}
    e = G.R.evaluate(padded, G.CALS)
    r["alt_expected"] = [{"reading": "M2 read zero-pads a short dense grid: the missing minutes read as 0", "expected": G.strip(e)}]
    rows.append(r)
    V(46, ge=0, n=30, const=True, now_units=96_000_000, m=6, cur=130, X=5, tags=["zero_range", "x_differs"], rules=("R-46",), derivation="constant column, x differs: zero_range_history")
    V(47, ge=2, n=40, m=10, cur=130, x_obj=C.tag_decimal("5"), tags=["tagged_decimal", "structural", "type_first"], rules=("R-65", "R-67"), derivation="Decimal X: malformed_type")
    V(48, ge=2, n=40, m=-5, cur=130, X=5, tags=["structural", "minute_out_of_range"], rules=("R-54",), derivation="minute -5")
    # ATM form (owner decision 2): iv_form default atm, series atm_iv (minute series on the session grid)
    O = "__omit__"
    A_ = lambda i_, **kw: V(i_, iv_form=kw.pop("iv_form", "atm"), **kw)
    A_(49, ge=12, n=252, m=10, cur=270, X=5, iv_form=O, tags=["atm_form", "default_form", "rank", "boundary", "n252"], derivation="iv_form omitted: default atm, series atm_iv; 12/252 <= 1/20")
    A_(50, ge=13, n=252, m=10, cur=270, X=5, tags=["atm_form", "rank", "boundary", "n252"], derivation="explicit atm; 13/252 > 1/20")
    A_(51, ge=126, n=252, m=0, cur=270, X=50, tags=["atm_form", "exact_boundary", "n252"], derivation="126/252 == 1/2 fires; minute 0")
    A_(52, ge=15, n=252, m=11, cur=270, X=6, tags=["atm_form", "rank", "n252", "lookback"], derivation="252 look-back, minute 11; 15/252 <= 6/100")
    A_(53, ge=5, le=98, n=100, m=10, cur=130, X=5, tags=["atm_form", "ties", "exact_boundary"], derivation="2 above plus 3 equal = 5/100 fires")
    A_(54, ge=6, le=97, n=100, m=10, cur=130, X=5, tags=["atm_form", "ties", "boundary"], derivation="6/100 no")
    A_(55, ge=1, n=20, m=10, cur=130, X=5, tags=["atm_form", "n20", "exact_boundary"], derivation="1/20 fires")
    A_(56, ge=1, n=19, m=10, cur=130, X=5, tags=["atm_form", "n19", "insufficient"], rules=("R-44", "R-47"), derivation="19 < 20")
    A_(57, ge=2, n=40, m=14, cur=130, X=5, tags=["atm_form", "half_day", "skipped"], rules=RB + ("R-55",), derivation="12-minute half-days have no minute 14: skipped")
    A_(58, ge=2, n=40, m=12, cur=130, X=5, tags=["atm_form", "half_day", "first_missing_minute"], rules=RB + ("R-55",), derivation="minute 12 skipped on half-days")
    A_(59, ge=2, n=24, miss=6, m=5, cur=130, X=5, tags=["atm_form", "missing_sessions"], rules=RB + ("R-51",), derivation="6 sessions without a record skipped")
    A_(60, ge=2, n=22, inc=4, m=5, cur=130, X=5, tags=["atm_form", "incomplete_day"], rules=RB + ("R-47",), derivation="4 incomplete skipped")
    A_(61, ge=2, n=40, m=7, cur=130, X=5, lookahead=(96_100_000, 96_200_000), today=(96_300_000, 0), tags=["atm_form", "today_excluded", "alignment"], rules=RB + ("R-47",), derivation="today and later sessions never read")
    A_(62, n=30, const=True, m=6, cur=130, X=5, tags=["atm_form", "zero_range"], rules=("R-46",), derivation="constant column: zero_range_history")
    A_(63, ge=2, n=40, m=30, cur=130, X=5, tags=["atm_form", "structural", "minute_out_of_range"], rules=("R-54",), derivation="minute 30")
    A_(64, ge=2, n=40, m=10, cur=130, X=5, delayed=True, tags=["atm_form", "delayed"], rules=("R-58",), derivation="live only: delayed_feed_tag")
    A_(65, ge=2, n=40, m=10, cur=130, X=5, now_unavail="no_atm_strike", tags=["atm_form", "upstream_reason"], rules=("R-81",), derivation="ATM IV unavailable (no_atm_strike) propagates")
    A_(66, ge=3, n=60, m=10, cur=140, X=5, maxs=30, tags=["atm_form", "cap"], rules=RB + ("R-44",), derivation="newest 30 usable sessions only")
    A_(67, ge=1, n=10, m=10, cur=130, X=5, now_unavail="no_atm_strike", tags=["atm_form", "upstream_reason", "gate_order", "insufficient"], rules=("R-81",), derivation="two conditions: unavailable and 10 sessions")
    A_(68, ge=2, n=40, m=10, cur=130, X=5, series_metric="iv30", tags=["atm_form", "no_mixing"], rules=("R-81",), derivation="records are the iv30 series, request form atm: a different series, no mixing: insufficient_history")
    A_(69, ge=2, n=40, m=10, cur=130, X=5, iv_form="30d", series_metric="atm_iv", tags=["30d_form", "no_mixing"], rules=("R-81",), derivation="records are the atm_iv series, request form 30d: insufficient_history")
    # selector validation
    A_(70, ge=2, n=40, m=10, cur=130, X=5, iv_form="30d", tags=["selector", "30d_form"], rules=("R-81",), derivation="explicit 30d reads the iv30 series and echoes iv_form 30d")
    A_(71, ge=2, n=40, m=10, cur=130, X=5, iv_form="ATM", tags=["selector", "structural"], rules=("R-81",), derivation="iv_form is case sensitive: iv_form_not_allowed")
    A_(72, ge=2, n=40, m=10, cur=130, X=5, iv_form="", tags=["selector", "structural"], rules=("R-81",), derivation="empty string: iv_form_not_allowed")
    A_(73, ge=2, n=40, m=10, cur=130, X=5, iv_form="90d", tags=["selector", "structural"], rules=("R-81",), derivation="unknown form: iv_form_not_allowed")
    A_(74, ge=2, n=40, m=10, cur=130, X=5, iv_form=5, tags=["selector", "structural", "type_first"], rules=("R-67",), derivation="int iv_form: malformed_type")
    A_(75, ge=2, n=40, m=10, cur=130, X=5, iv_form=None, tags=["selector", "structural", "type_first"], rules=("R-67",), derivation="None iv_form: malformed_type")
    A_(76, ge=2, n=40, m=10, cur=130, X=5, iv_form=O, tags=["atm_form", "default_form", "selector"], rules=("R-81",), derivation="iv_form omitted: default atm, params echo iv_form atm")
    A_(77, ge=2, n=40, m=10, cur=130, X=101, iv_form="90d", tags=["selector", "precedence_pair", "structural"], rules=("R-66", "R-152"), derivation="position 13 (iv_form_not_allowed) before position 15 (X 101)")
    A_(78, ge=2, n=40, m=10, cur=130, X=5, mins=0, iv_form="90d", tags=["selector", "precedence_pair", "structural"], rules=("R-66", "R-152"), derivation="position 10 (min_sessions 0, malformed_type) before position 13 (iv_form_not_allowed)")
    A_(79, ge=2, n=40, m=40, cur=130, X=5, iv_form="90d", tags=["selector", "precedence_pair", "structural"], rules=("R-66", "R-152"), derivation="position 13 before position 16 (minute 40 out of range)")
    A_(80, ge=2, n=40, m=10, cur=130, X=5, iv_form=7, mins=0, tags=["selector", "precedence_pair", "structural", "type_first"], rules=("R-66", "R-67"), derivation="min_sessions 0 and a wrong-typed iv_form: both malformed_type, one code")
    for r in rows:
        i = int(r["id"][-3:])
        if i in (71, 72, 73, 74, 75, 77, 78, 79, 80):
            r["expected"].pop("series_id", None)  # R-153 follow-up: series_id is arbitrary on a structural error
    return rows


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    rows = build()
    C.write_dataset(os.path.join(here, "m3a_cases_V3.json"), G.header("V3"), rows)
    return rows


if __name__ == "__main__":
    print(len(main()))

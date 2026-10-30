"""Generator for family V9 (M3A-8): 25-delta skew (put minus call, annual decimal) percentile against its own history. SYNTHETIC.
The skew now value is the difference of the UNROUNDED float put and call 25-delta IVs, rounded once (R-95)."""
import os

import gen_m3a_g4 as G
import m3a_common as C

FAM = "V9"
R_BASE = ("R-53", "R-45", "R-50", "R-95")
OLD = list(range(70_000_000, 70_000_030))  # older values above any planted skew


def build():
    rows = []

    def P(n_id, **kw):
        rid = "M3A-V9-%03d" % n_id
        kw.setdefault("rules", R_BASE)
        kw.setdefault("skew", True)
        if "ties" not in kw.get("tags", ()) and "n" in kw and "ge" in kw and "vals_override" not in kw:
            kw["le"] = kw["n"] - kw["ge"]
        rows.append(G.pct_row(rid, FAM, "M3A-8", G.rng_for(rid), **kw))

    P(1, ge=12, le=0, n=252, X=5, mins=20, maxs=252, tags=["rank", "top", "boundary", "n252"], derivation="12/252=1/21 <= 1/20")
    P(2, ge=13, le=0, n=252, X=5, tags=["rank", "top", "boundary", "n252"], derivation="13/252 > 1/20")
    P(3, ge=2, le=0, n=252, X=1, tags=["rank", "top", "boundary", "n252"], derivation="2/252 <= 1/100")
    P(4, ge=3, le=0, n=252, X=1, tags=["rank", "top", "boundary", "n252"], derivation="3/252 > 1/100")
    P(5, ge=15, le=0, n=252, X=6, tags=["rank", "top", "boundary", "n252"], derivation="15/252 <= 6/100")
    P(6, ge=16, le=0, n=252, X=6, tags=["rank", "top", "boundary", "n252"], derivation="16/252 > 6/100")
    P(7, ge=126, le=0, n=252, X=50, tags=["rank", "top", "exact_boundary", "n252"], derivation="126/252 == 50/100 fires")
    P(8, ge=127, le=0, n=252, X=50, tags=["rank", "top", "boundary", "n252"], derivation="127/252 > 1/2")
    P(9, ge=3, le=252, n=252, X=5, tags=["ties", "top", "ties_top"], derivation="3 copies of the maximum equal x: ties count in upper_share")
    P(10, ge=5, le=98, n=100, X=5, tags=["ties", "top", "exact_boundary"], derivation="2 above plus 3 equal = 5/100 fires")
    P(11, ge=6, le=97, n=100, X=5, tags=["ties", "top", "boundary"], derivation="3 above plus 3 equal = 6/100 no")
    P(12, ge=95, le=0, n=100, X=5, tail="bottom", tags=["bottom", "exact_boundary"], derivation="lower_share 5/100 fires")
    P(13, ge=94, le=0, n=100, X=5, tail="bottom", tags=["bottom", "boundary"], derivation="lower_share 6/100 no")
    P(14, ge=242, le=12, n=252, X=5, tail="bottom", tags=["bottom", "ties", "n252"], derivation="ties at x, le=12 of 252 fires")
    P(15, ge=1, le=0, n=20, X=5, tags=["n20", "exact_boundary", "defaults"], plain_params={}, derivation="defaults; 1/20 == 5/100")
    P(16, ge=1, le=0, n=21, X=5, tags=["n21"], derivation="1/21 <= 1/20")
    P(17, ge=1, le=0, n=19, X=5, tags=["n19", "insufficient"], rules=("R-44", "R-47"), derivation="19 < 20")
    P(18, ge=2, le=0, n=30, X=5, maxs=30, prefix=OLD, tags=["cap", "max_sessions"], rules=R_BASE + ("R-44",), derivation="60 stored, max_sessions 30: newest 30 only")
    P(19, ge=0, le=0, n=30, const=True, X=5, tags=["zero_range", "negative_values"], rules=("R-46",), derivation="constant skew history: zero_range_history",
      vals_override=[-3_000_000] * 30, now_units=-3_000_000)
    P(20, ge=0, le=0, n=30, vals_override=[-3_000_000] * 29 + [-2_999_999], now_units=-3_000_000, X=5, tags=["zero_range_near", "ties"], rules=("R-46", "R-50"),
      derivation="range of 1 unit: available")
    P(21, ge=2, le=0, n=22, miss=8, X=5, tags=["missing_days", "r51"], rules=R_BASE + ("R-51",), derivation="22 usable among 30 calendar sessions")
    P(22, ge=1, le=0, n=19, miss=11, X=5, tags=["missing_days", "r51", "insufficient"], rules=("R-51", "R-47"), derivation="19 usable among 30")
    P(23, ge=2, le=0, n=24, inc=5, X=5, tags=["incomplete_day", "r47"], rules=R_BASE + ("R-47",), derivation="5 incomplete skipped")
    P(24, ge=2, le=0, n=40, lookahead=(70_100_000, 70_200_000), today=(70_300_000, 1), X=5, tags=["today_excluded", "lookahead"], rules=R_BASE + ("R-47",),
      derivation="today and later stored sessions never read")
    P(25, ge=2, le=0, n=50, mode="close", complete=True, X=5, tags=["close", "end_of_day"], rules=R_BASE + ("R-56",), derivation="close mode sealed")
    P(26, ge=2, le=0, n=50, mode="close", complete=False, X=5, tags=["close", "session_not_complete"], rules=("R-47", "R-56"), derivation="unsealed")
    P(27, ge=2, le=0, n=50, delayed=True, X=5, tags=["delayed", "intraday"], rules=("R-58",), derivation="intraday V9 delayed: delayed_feed_tag")
    P(28, ge=2, le=0, n=50, delayed=True, mode="close", complete=True, X=5, tags=["delayed", "close", "end_of_day"], rules=("R-56", "R-58", "R-63"), derivation="close delayed labelled")
    P(29, ge=2, le=0, n=50, X=101, tags=["structural", "threshold"], rules=("R-72",), derivation="X 101")
    P(30, ge=2, le=0, n=50, X=True, tags=["structural", "type_first"], rules=("R-67", "R-72"), derivation="bool X is not an int: malformed_type")
    P(31, ge=2, le=0, n=50, X=-1, maxs=0, tags=["structural", "precedence_pair"], rules=("R-66", "R-72"), derivation="max_sessions 0 (position 10) before X -1 (position 15)")
    P(32, ge=1, le=0, n=40, x_obj=C.tag_fraction("5/2"), tags=["tagged_fraction", "exact_boundary"], rules=R_BASE + ("R-65",), derivation="X=5/2: 1/40 fires")
    # signs
    P(33, ge=0, le=0, n=40, vals_override=[-9_000_000 - i * 1000 for i in range(40)], now_units=1_000, X=5, tags=["sign", "extreme"], derivation="all prior skews negative, x positive: upper_share 0")
    P(34, ge=0, le=0, n=40, vals_override=[9_000_000 + i * 1000 for i in range(40)], now_units=-1_000, X=5, tail="bottom", tags=["sign", "extreme"], derivation="all prior positive, x negative: lower_share 0, bottom fires")
    P(35, ge=0, le=0, n=41, vals_override=[(i - 20) * 100_000 for i in range(41)], now_units=0, X=50, tags=["sign", "x_zero", "ties"], derivation="history -2,000,000 to 2,000,000 step 100,000; x = 0 ties the middle value")
    # rounding of the derived series (R-49, R-95)
    P(36, ge=0, le=0, n=32, vals_override=[9_999_999] * 12 + [10_000_000] * 12 + [8_000_000] * 4 + [11_000_000] * 4, now_units=10_000_000, X=50,
      put_call={"put25_iv": 0.2000000049, "call25_iv": 0.1000000051}, tags=["round_once", "units", "ties"], rules=("R-49", "R-95"),
      derivation="put-call = 0.0999999998 -> 10,000,000 units; rounding the parts first would give 9,999,999")
    P(37, ge=0, le=0, n=24, vals_override=[195_312] * 6 + [195_313] * 6 + [100_000] * 6 + [300_000] * 6, now_units=195_312, X=50,
      put_call={"put25_iv": 0.5, "call25_iv": 0.498046875}, tags=["round_once", "half_even", "units", "ties"], rules=("R-49", "R-95"),
      derivation="difference exactly 1/512 = 0.001953125: tie at 8 decimals, half to even gives 195,312 not 195,313")
    P(38, ge=0, le=0, n=30, vals_override=[-195_312] * 5 + [-195_313] * 5 + [-100_000] * 10 + [100_000] * 10, now_units=-195_312, X=50,
      put_call={"put25_iv": 0.498046875, "call25_iv": 0.5}, tags=["round_once", "half_even", "negative", "units", "ties"], rules=("R-49", "R-95"),
      derivation="difference exactly -1/512: half to even gives -195,312")
    P(39, ge=0, le=0, n=25, vals_override=[0] * 5 + [-1000] * 10 + [1000] * 10, now_units=0, X=50,
      put_call={"put25_iv": 0.25, "call25_iv": 0.250000004}, tags=["round_once", "negative_zero", "units", "ties"], rules=("R-49", "R-95"),
      derivation="difference -4e-9 rounds to 0 units: x is 0.00000000 (no minus sign), ties the 5 zeros")
    # upstream reasons and labels
    P(40, ge=2, le=0, n=50, X=5, now_unavail="no_delta_bracket", tags=["upstream_reason"], rules=("R-16", "R-21"), derivation="M3A-7 value unavailable: no_delta_bracket propagates")
    P(41, ge=2, le=0, n=50, X=5, now_unavail="low_surface_coverage", tags=["upstream_reason"], rules=("R-20",), derivation="low_surface_coverage propagates")
    P(42, ge=2, le=0, n=50, X=5, now_unavail="price_out_of_bounds", tags=["upstream_reason", "solver_reason"], rules=("R-86",), derivation="solver reason propagates verbatim")
    P(43, ge=2, le=0, n=10, X=5, now_unavail="no_delta_bracket", tags=["upstream_reason", "gate_order", "insufficient"], rules=("R-16",), derivation="two conditions: unavailable skew and 10 sessions")
    P(44, ge=2, le=0, n=50, X=5, model_label=C.APPROX, tags=["label", "approximate"], rules=("R-11", "R-63"), derivation="approximate label echoed")
    P(45, ge=2, le=0, n=50, X=5, ring_lane="etf_index", tags=["lane", "lane_read"], rules=("R-73",), force_pending="PENDING-RULING:D5", derivation="ring lane etf_index read under stock")
    rows[-1]["alt_expected"] = [{"reading": "R-73 text: history lane mismatch is lane_mismatch",
                                  "expected": {"status": "invalid_input", "reason": None, "code": "lane_mismatch", "value": None, "fired": None}}]
    P(46, ge=2, le=0, n=50, X=5, session_in_cal=False, tags=["structural", "session_not_in_calendar"], rules=("R-66",), derivation="session missing from calendar")
    P(47, ge=0, le=0, n=30, vals_override=[-3_000_000] * 30, now_units=5_000_000, X=5, tags=["zero_range", "x_differs", "negative_values"], rules=("R-46",), derivation="constant skew history, x differs: still zero_range_history")
    P(48, ge=2, le=0, n=50, x_obj=C.tag_decimal("5"), tags=["tagged_decimal", "structural", "type_first"], rules=("R-65", "R-67"), derivation="Decimal X: malformed_type")
    P(49, ge=1, le=0, n=10, mode="close", complete=False, X=5, tags=["close", "gate_order", "insufficient"], rules=("R-47", "R-56"), derivation="two conditions: 10 sessions and unsealed")
    P(50, ge=3, le=0, n=60, miss=10, maxs=30, X=5, mins=20, tags=["cap", "missing_days", "d3"], rules=R_BASE + ("R-44", "R-51"),
      derivation="60 usable and 10 missing days, max_sessions 30: last 30 available sessions")
    # OWNER DECISION 3: delta_convention in {spot, forward}, default spot; series skew25 (spot), skew25_fwd (forward)
    RC = R_BASE + ("R-53",)
    P(51, ge=2, le=0, n=50, X=5, conv="__omit__", tags=["convention", "default_spot"], rules=RC, derivation="delta_convention omitted: spot, series skew25, echoed")
    P(52, ge=2, le=0, n=50, X=5, conv="spot", tags=["convention", "spot"], rules=RC, derivation="explicit spot")
    P(53, ge=2, le=0, n=50, X=5, conv="forward", tags=["convention", "forward"], rules=RC, derivation="forward convention reads skew25_fwd records")
    P(54, ge=1, le=0, n=19, X=5, conv="forward", tags=["convention", "forward", "insufficient"], rules=RC, derivation="19 forward sessions: insufficient_history")
    P(55, ge=5, le=98, n=100, X=5, conv="forward", tags=["convention", "forward", "ties", "exact_boundary"], rules=RC, derivation="forward: 2 above plus 3 equal = 5/100 fires")
    P(56, ge=2, le=0, n=50, X=5, conv="forward", records_conv="spot", tags=["convention", "convention_mismatch"], rules=RC, derivation="forward request, stored skew25_fwd records are spot: convention_mismatch at store read")
    P(57, ge=2, le=0, n=50, X=5, conv="spot", records_conv="forward", tags=["convention", "convention_mismatch"], rules=RC, derivation="spot request, stored records are forward: convention_mismatch")
    P(58, ge=2, le=0, n=50, X=5, conv="Forward", tags=["convention", "structural"], rules=RC, derivation="case sensitive: convention_not_allowed")
    P(59, ge=2, le=0, n=50, X=5, conv="", tags=["convention", "structural"], rules=RC, derivation="empty string: convention_not_allowed")
    P(60, ge=2, le=0, n=50, X=5, conv=7, tags=["convention", "structural", "type_first"], rules=RC, derivation="int convention: malformed_type")
    P(61, ge=2, le=0, n=50, X=5, conv=None, tags=["convention", "structural", "type_first"], rules=RC, derivation="None convention: malformed_type")
    P(62, ge=2, le=0, n=50, X=5, conv="forward", mode="close", complete=True, delayed=True, tags=["convention", "forward", "close", "delayed"], rules=RC + ("R-58",), derivation="forward close form, delayed: labelled delayed")
    P(63, ge=0, le=0, n=30, vals_override=[-3_000_000] * 30, now_units=-3_000_000, X=5, conv="forward", tags=["convention", "forward", "zero_range"], rules=RC + ("R-46",), derivation="constant forward skew history: zero_range_history")
    P(64, ge=2, le=0, n=50, X=5, conv=True, tags=["convention", "structural", "type_first"], rules=RC, derivation="bool convention: malformed_type")
    P(65, ge=2, le=0, n=50, X=101, conv="Forward", tags=["convention", "precedence_pair", "structural"], rules=RC + ("R-66",), derivation="position 13 (convention_not_allowed) before position 15 (X 101)")
    P(66, ge=2, le=0, n=50, X=5, mins=0, conv="Forward", tags=["convention", "precedence_pair", "structural"], rules=RC + ("R-66",), derivation="position 10 (malformed_type) before position 13")
    P(67, ge=2, le=0, n=50, X=101, conv="forward", records_conv="spot", tags=["convention", "precedence_pair", "convention_mismatch"], rules=RC + ("R-66", "R-160"), derivation="position 15 (X 101) before position 17 (convention_mismatch)")
    P(68, ge=2, le=0, n=50, X=5, conv="forward", records_conv="spot", delayed=True, tags=["convention", "precedence_pair", "convention_mismatch", "delayed"], rules=RC + ("R-66", "R-160"), derivation="position 17 (convention_mismatch) before position 18 (delayed_feed_tag)")
    P(69, ge=2, le=0, n=50, X=5, conv="spot", records_conv="forward", delayed=True, tags=["convention", "precedence_pair", "convention_mismatch", "delayed"], rules=RC + ("R-66", "R-160"), derivation="spot request on forward records, delayed: convention_mismatch (17) before delayed_feed_tag (18)")
    return rows


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    rows = build()
    C.write_dataset(os.path.join(here, "m3a_cases_V9.json"), G.header("V9"), rows)
    return rows


if __name__ == "__main__":
    print(len(main()))

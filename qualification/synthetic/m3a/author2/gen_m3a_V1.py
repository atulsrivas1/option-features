"""Generator for family V1 (M3A-1): 30-day IV percentile against its own prior session-close history. SYNTHETIC."""
import os

import gen_m3a_g4 as G
import m3a_common as C

FAM = "V1"
R_BASE = ("R-42", "R-44", "R-45", "R-50")
OLD = list(range(96_000_000, 96_000_030))  # older values above any planted x


def build():
    rows = []

    def P(n_id, **kw):
        rid = "M3A-V1-%03d" % n_id
        kw.setdefault("rules", R_BASE)
        if "ties" not in kw.get("tags", ()) and "n" in kw and "ge" in kw:
            kw["le"] = kw["n"] - kw["ge"]  # no value equal to x unless the row is a tie row
        rows.append(G.pct_row(rid, FAM, "M3A-1", G.rng_for(rid), **kw))

    # A. n = 252, top X percent, upper_share against X/100 at and beside the boundary
    P(1, ge=12, le=241, n=252, X=5, mins=20, maxs=252, tags=["rank", "top", "boundary", "n252"], derivation="12/252=1/21 <= 1/20")
    P(2, ge=13, le=240, n=252, X=5, mins=20, maxs=252, tags=["rank", "top", "boundary", "n252"], derivation="13/252 > 1/20")
    P(3, ge=2, le=251, n=252, X=1, tags=["rank", "top", "boundary", "n252"], derivation="2/252=1/126 <= 1/100")
    P(4, ge=3, le=250, n=252, X=1, tags=["rank", "top", "boundary", "n252"], derivation="3/252=1/84 > 1/100")
    P(5, ge=15, le=238, n=252, X=6, tags=["rank", "top", "boundary", "n252"], derivation="15/252=5/84 <= 6/100")
    P(6, ge=16, le=237, n=252, X=6, tags=["rank", "top", "boundary", "n252"], derivation="16/252=4/63 > 6/100")
    P(7, ge=126, le=127, n=252, X=50, tags=["rank", "top", "boundary", "exact_boundary", "n252"], derivation="126/252=1/2 == 50/100 fires (inclusive, R-35)")
    P(8, ge=127, le=126, n=252, X=50, tags=["rank", "top", "boundary", "n252"], derivation="127/252 > 1/2")
    # B. ties
    P(9, ge=3, le=252, n=252, X=5, tags=["ties", "top", "ties_top"], rules=R_BASE, derivation="x equals the maximum, 3 copies: ties count in upper_share and rank_le")
    P(10, ge=5, le=98, n=100, X=5, tags=["ties", "top", "exact_boundary"], derivation="2 above plus 3 equal = 5/100 == X/100 fires")
    P(11, ge=6, le=97, n=100, X=5, tags=["ties", "top", "boundary"], derivation="3 above plus 3 equal = 6/100 > X/100")
    # C. bottom X percent
    P(12, ge=95, le=5, n=100, X=5, tail="bottom", tags=["bottom", "exact_boundary"], derivation="lower_share=5/100 == X/100 fires; upper_share is also returned")
    P(13, ge=94, le=6, n=100, X=5, tail="bottom", tags=["bottom", "boundary"], derivation="6/100 > 5/100")
    P(14, ge=242, le=12, n=252, X=5, tail="bottom", tags=["bottom", "ties", "n252"], derivation="2 ties at x: le=12 -> 12/252 <= 1/20")
    # D. 19, 20, 21 sessions and the defaults
    P(15, ge=1, le=20, n=20, X=5, tags=["n20", "exact_boundary", "defaults"], derivation="defaults X 5, min 20, max 252, mode intraday, tail top; 1/20 == 5/100",
      plain_params={})
    P(16, ge=2, le=19, n=20, X=5, tags=["n20", "boundary"], derivation="2/20 > 5/100")
    P(17, ge=1, le=21, n=21, X=5, tags=["n21"], derivation="1/21 <= 1/20")
    P(18, ge=1, le=19, n=19, X=5, tags=["n19", "insufficient"], rules=("R-44", "R-47"), derivation="19 prior sessions < min_sessions 20")
    # E. cap, min_sessions
    P(19, ge=2, le=29, n=30, X=5, maxs=30, prefix=OLD, tags=["cap", "max_sessions"], rules=R_BASE + ("R-44",),
      derivation="60 stored, max_sessions 30: the 30 most recent only; the 30 older values all above x would change the share")
    P(20, ge=1, le=12, n=12, X=5, mins=10, tags=["min_sessions_param"], derivation="min_sessions 10 with 12 available")
    P(21, ge=1, le=22, n=22, X=5, mins=30, tags=["min_sessions_param", "insufficient"], rules=("R-44", "R-47"), derivation="22 < min_sessions 30")
    # F. zero range
    P(22, ge=0, le=0, n=30, const=True, X=5, tags=["zero_range"], rules=("R-46",), derivation="constant 30-session history: unavailable zero_range_history (design VR P3; exception to M2 Q2)")
    P(23, ge=0, le=0, n=252, const=True, now_units=96_000_000, X=5, tags=["zero_range", "n252"], rules=("R-46",), derivation="constant history, x above the constant: still unavailable")
    P(24, ge=0, le=0, n=30, vals_override=[40_000_000] * 29 + [40_000_001], now_units=40_000_000, X=5, tags=["zero_range_near", "ties"], rules=("R-46", "R-50"),
      derivation="range of 1 unit is not zero range: available; x ties 29 values")
    P(25, ge=0, le=0, n=19, const=True, X=5, tags=["zero_range", "insufficient", "gate_order"], rules=("R-46", "R-47"), derivation="two conditions: 19 constant sessions")
    # G. missing and incomplete days (R-51)
    P(26, ge=2, le=21, n=22, miss=8, X=5, tags=["missing_days", "r51"], rules=R_BASE + ("R-51",), derivation="22 usable among 30 calendar sessions, no zero padding")
    P(27, ge=1, le=20, n=20, miss=10, X=5, tags=["missing_days", "r51", "n20"], rules=R_BASE + ("R-51",), derivation="exactly 20 usable among 30 calendar sessions")
    P(28, ge=1, le=18, n=18, miss=12, X=5, tags=["missing_days", "r51", "insufficient"], rules=("R-51", "R-47"), derivation="18 usable among 30 calendar sessions: insufficient_history")
    P(29, ge=2, le=23, n=24, inc=5, X=5, tags=["incomplete_day", "r47"], rules=R_BASE + ("R-47",), derivation="5 incomplete stored sessions skipped (decoys on both sides of x)")
    P(30, ge=1, le=19, n=19, inc=3, X=5, tags=["incomplete_day", "insufficient"], rules=("R-47",), derivation="19 complete plus 3 incomplete stored: incomplete never count toward min_sessions")
    P(31, ge=2, le=39, n=40, lookahead=(96_100_000, 96_200_000, 1_000), today=(96_300_000, 1), X=5, tags=["today_excluded", "lookahead"], rules=R_BASE + ("R-47",),
      derivation="stored records for today and later sessions are never read (strictly before the session)")
    # H. modes, completeness, delayed (R-56, R-58)
    P(32, ge=2, le=49, n=50, mode="close", X=5, complete=True, tags=["close", "end_of_day"], rules=R_BASE + ("R-56",), derivation="close mode, sealed session: form end_of_day")
    P(33, ge=2, le=49, n=50, mode="close", X=5, complete=False, tags=["close", "session_not_complete"], rules=("R-47", "R-56"), derivation="close mode on an unsealed session")
    P(34, ge=1, le=9, n=10, mode="close", X=5, complete=False, tags=["close", "gate_order", "insufficient"], rules=("R-47", "R-56"), derivation="two conditions: 10 sessions and unsealed")
    P(35, ge=2, le=49, n=50, X=5, delayed=True, tags=["delayed", "intraday"], rules=("R-58",), derivation="intraday V1 under a delayed tag is invalid_input delayed_feed_tag (exception to design 'unavailable')")
    P(36, ge=2, le=49, n=50, mode="close", X=5, complete=True, delayed=True, tags=["delayed", "close", "end_of_day"], rules=("R-56", "R-58", "R-63"),
      derivation="close form is computed and labelled delayed")
    # I. structural (single and pair)
    P(37, ge=2, le=49, n=50, X=101, tags=["structural", "threshold"], rules=("R-72",), derivation="X above 100: threshold_out_of_range")
    P(38, ge=2, le=49, n=50, X=5.0, tags=["structural", "type_first"], rules=("R-67", "R-72"), derivation="float X: malformed_type (M2 parameter rule)")
    P(39, ge=2, le=49, n=50, X=101, mins=0, tags=["structural", "precedence_pair"], rules=("R-66", "R-72"),
      derivation="min_sessions 0 (malformed_type, position 10) and X 101 (position 15): the first listed code is reported")
    P(40, ge=1, le=40, n=40, x_obj=C.tag_fraction("5/2"), tags=["tagged_fraction", "exact_boundary", "x_param"], rules=R_BASE + ("R-65",),
      derivation="X = 5/2 percent as a tagged Fraction: 1/40 == 25/1000 fires")
    P(41, ge=1, le=40, n=40, x_obj=C.tag_decimal("2.5"), tags=["tagged_decimal", "structural", "type_first"], rules=("R-65", "R-67"), derivation="Decimal X is not an accepted type: malformed_type")
    P(42, ge=1, le=40, n=40, session_in_cal=False, tags=["structural", "session_not_in_calendar"], rules=("R-66",), derivation="current session missing from the calendar (view read position 1)")
    # J. extremes, labels, upstream reason, lane
    P(43, ge=0, le=60, n=60, now_units=97_000_000, X=0, tags=["extreme", "x_zero"], rules=R_BASE, derivation="x above every prior value: upper_share 0, X=0 fires (0 <= 0)")
    P(44, ge=60, le=0, n=60, now_units=1_000_000, X=100, tags=["extreme", "x_hundred"], rules=R_BASE, derivation="x below every prior value: upper_share 1 <= 100/100 fires")
    P(45, ge=2, le=49, n=50, X=5, model_label=C.APPROX, tags=["label", "approximate"], rules=("R-11", "R-63"), derivation="model label echoed verbatim")
    P(46, ge=2, le=49, n=50, X=5, now_unavail="no_bracketing_expiry", tags=["upstream_reason"], rules=("R-81",), derivation="M3A-0 iv30 unavailable: the reason propagates")
    P(47, ge=1, le=9, n=10, X=5, now_unavail="no_bracketing_expiry", tags=["upstream_reason", "gate_order", "insufficient"], rules=("R-81",),
      derivation="two conditions: iv30 unavailable and 10 sessions")
    P(48, ge=2, le=49, n=50, X=5, ring_lane="etf_index", tags=["lane", "lane_read"], rules=("R-73",), force_pending="PENDING-RULING:D5",
      derivation="history ring lane etf_index read under request lane stock",
      )
    # D5 alternative: lane_mismatch as a structural result at read
    rows[-1]["alt_expected"] = [{"reading": "R-73 text: history lane mismatch is lane_mismatch",
                                  "expected": {"status": "invalid_input", "reason": None, "code": "lane_mismatch", "value": None, "fired": None}}]
    P(49, ge=0, le=0, n=30, const=True, now_units=5_000_000, X=5, tags=["zero_range", "x_differs"], rules=("R-46",), derivation="constant history, x below the constant: zero range is judged on the history alone")
    P(50, ge=1, le=14, n=15, mode="close", complete=False, X=5, tags=["close", "gate_order", "insufficient"], rules=("R-47", "R-56"), derivation="two conditions: 15 sessions and unsealed")
    P(51, ge=0, le=0, n=30, const=True, mode="close", complete=False, X=5, tags=["close", "gate_order", "zero_range"], rules=("R-46", "R-47", "R-56"), derivation="two conditions: constant history and unsealed")
    P(52, ge=3, le=0, n=60, miss=10, maxs=30, X=5, mins=20, tags=["cap", "missing_days", "d3"], rules=R_BASE + ("R-44", "R-51"),
      derivation="60 usable and 10 missing days, max_sessions 30: last 30 available sessions (a 30-calendar-session window would hold fewer)")
    return rows


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    rows = build()
    C.write_dataset(os.path.join(here, "m3a_cases_V1.json"), G.header("V1"), rows)
    return rows


if __name__ == "__main__":
    print(len(main()))

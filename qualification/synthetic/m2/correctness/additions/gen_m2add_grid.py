"""Additions for story A: trade-to-grid builder (output M2-GRID): 16 rows. Grid point i is at open + 60 s x i; its value is the
metric over the closed window [t_i - W, t_i] of eligible session prints (open <= t <= close); total is over all eligible session prints."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import m2add_oracle as A  # noqa: E402
from m2common import *  # noqa: E402,F401,F403
import m2common as C  # noqa: E402

A.install()
EL = S(1200)
LC = dict(CONTRACTS)
LC["XC1"] = K("C", 1000000, EXP1, lane="etf_index")


def build(rng):
    R = Rows("addgrid", "M2A-GRID")
    T = ["additions", "grid_builder"]

    def g(prints, metric, W, tags, minutes=12, contract_id=None, lane=None, con=None, pending=None):
        ps = [p(*a) if not isinstance(a, list) else a for a in prints]
        prm = {"metric": metric, "window_s": W}
        if contract_id:
            prm["contract_id"] = contract_id
        if lane:
            prm["lane"] = lane
        R.add("M2-GRID", "story A trade-to-grid build (M2-B18); contract 2 Grid", "Q1,Q15",
              mkin(ps, contracts=con or CONTRACTS, sess=session("2026-06-01", EL, minutes)), prm, tags=T + tags, pending=pending)

    def p(cid, t_s, usd_, size=10, **kw):
        return pp(cid, S(t_s) - EL, usd_, size=size, **kw)

    def q(cid, t_s, size, **kw):
        return pr(cid, S(t_s) - EL, "1.0000", size, **kw)

    base = [p("C1", 0, 10000), p("C1", 30, 5000), p("P1", 60, 2000), p("C2", 125, 1000)]
    g(base, "premium", 60, ["premium", "dense"])                                           # 1
    g(base, "premium", 300, ["premium", "dense", "window_len"])                            # 2
    vol = [q("C1", 0, 7), q("P1", 45, 3), q("P2", 60, 5), q("C2", 130, 11), q("C1", 599, 2)]
    g(vol, "contracts", 60, ["contracts"])                                                 # 3
    g(vol, "prints", 300, ["prints", "window_len"])                                        # 4
    g(vol, "put_volume", 60, ["put_volume"])                                               # 5
    g(vol, "call_volume", 300, ["call_volume", "window_len"])                              # 6
    g([q("C1", -30, 100), q("C1", Fr("-0.000000001"), 100), q("C1", 0, 1), q("C1", 59, 2)], "contracts", 60, ["preopen_excluded"])   # 7
    g([q("C1", 100, 1), q("C1", 721, 50), q("C1", 900, 50)], "contracts", 60, ["postclose_excluded"])                          # 8
    g([q("C1", 660, 1), q("C1", 720, 5), q("C1", Fr("720.000000001"), 50)], "contracts", 60, ["close_boundary"],
      pending="PENDING-RULING: AMB-A1 whether a print exactly at close belongs to the session total (interim: yes, closed [open, close])")   # 9
    g([q("C1", 10, 1), q("C1", 100, 2), q("C1", 250, 4), q("C1", 359, 8), q("C1", 361, 16), q("C1", 500, 32)], "contracts", 60, ["half_day", "grid_length"], minutes=6)  # 10 half-day grid
    g([q("C1", 10, 5), q("C1", 20, 7, mult=10), q("C1", 30, 9, excl=1), q("C1", 40, 11, mult=10, excl=1), q("P1", 50, 3)], "contracts", 60,
      ["nonstd_counted", "cond_excl_counted", "both_excl"])                                # 11
    g([q("C1", 10, 5), q("XC1", 20, 700), q("XC1", 70, 900)], "contracts", 60, ["lane"], con=LC)                               # 12 stock lane
    g([q("C1", 10, 5), q("XC1", 20, 700), q("XC1", 70, 900)], "contracts", 60, ["lane"], con=LC, lane="etf_index")             # 13 etf lane
    g([q("P1", 10, 1), q("C1", 20, 9), q("P1", 200, 2), q("P1", 200, 4, seq=9), q("P1", 700, 8)], "prints", 60, ["sparse", "contract_series", "ties"], contract_id="P1")   # 14
    g([q("C1", 10, 1), q("C1", 20, 2)], "contracts", 60, ["sparse", "contract_series", "no_prints"], contract_id="P2")         # 15 all zero
    g(base + [p("C1", 600, 4000)], "premium", 3600, ["premium", "window_len", "window_longer_than_session"])                   # 16
    g([q("C1", -45, 9, mult=10), q("C1", -20, 3), q("C1", 15, 2), q("C1", 80, 4, mult=10)], "contracts", 60, ["preopen_excluded", "nonstd_counted"])   # 17
    g([q("C1", 5, 2, excl=1), q("C1", 70, 6, mult=10, excl=1), q("C1", 75, 1), q("P1", 130, 3, excl=1)], "prints", 60, ["cond_excl_counted", "both_excl"])  # 18
    g([p("C1", 660, 1000), p("C1", 720, 2000), p("C1", Fr("720.000000001"), 9000)], "premium", 60, ["close_boundary", "premium"])      # 19
    g(base + [p("C1", 300, 700), p("P1", 400, 900)], "premium", 300, ["sparse", "contract_series", "premium"], contract_id="C1")   # 20
    g([q("C1", 665, 3), q("C1", 700, 4)], "contracts", 60, ["final_minute", "close_boundary"])                                      # 21
    g(base, "contracts", 3600, ["valid_from_beyond", "window_len", "window_longer_than_session"])                       # 22
    g([q("P1", 10, 1), q("P1", 200, 2), q("C1", 20, 5)], "prints", 3600, ["valid_from_beyond", "sparse", "contract_series"], contract_id="P1")   # 23
    assert len(R.rows) == 23, len(R.rows)
    return R.rows


if __name__ == "__main__":
    C.main_for("add_grid", "addgrid", build)

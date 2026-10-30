"""M2-11 F12 unusual episodes today: 48 rows (Q11, Q7, Q15). Points are the per-grid-point [P60, P900] ticks of M2-1."""
from m2common import *

PEND = "PENDING-RULING:Q11 AMB-5 (first/last/peak definition)"
PRE = "u" * 15          # grid points 0..14 are before open + 900 s: insufficient_window


def spec_pts(spec):
    out = []
    for ch in spec:
        if ch == "u":
            out.append(None)
        elif ch == "q":
            out.append([1000, 15000])            # ratio 1
        elif ch == "f":
            out.append([3000, 15000])            # ratio 3 (= N, fires)
        elif ch == "n":
            out.append([2999, 15000])            # just below N
        elif ch == "z":
            out.append([0, 0])                   # P900 = 0 -> zero_denominator -> unavailable
        elif ch.isdigit():
            out.append([1000 * int(ch), 15000])  # ratio = digit
        else:
            raise ValueError(ch)
    return out


def build(rng):
    R = Rows("F12", "M2-F12")

    def f12(spec, tags, kT=None, extra=0, el=None, gap=1, nep=1, N=3, prior=None, pts=None, pend=None, prm=None):
        points = spec_pts(spec) if pts is None else pts
        kT = len(points) - 1 if kT is None else kT
        e = S(60 * kT) + extra if el is None else el
        inp = {"t_ns": T0, "series_id": "SYN1", "session": session("2026-06-01", e, 390), "points": points}
        if prior is not None:
            inp["prior_session_points"] = spec_pts(prior)
        row = R.add("M2-11", "flow.md F12; matrix M2-11", "Q11", inp,
                    ({"N": N, "quiet_gap": gap, "n_episodes": nep, "grid_s": 60} if prm is None else prm), tags=["f12"] + list(tags))
        v = row["expected"]["value"]
        if v and v["episode_count"] >= 1:
            pass
        if pend:
            row["pending"] = pend
        return row

    f12(PRE + "q" * 5 + "f" + "q" * 5, ["single_episode"])                       # 1
    f12(PRE + "qq" + "fff" + "qq", ["multi_point_episode"])                      # 2
    f12(PRE + "qqfqfqq", ["gap1", "f12_gap", "back_to_back"])                    # 3 two episodes, one quiet between
    f12(PRE + "qqfqqfqq", ["gap1", "f12_gap"])                                   # 4
    f12(PRE + "fqfqfq", ["gap1", "f12_gap", "three_episodes"])                   # 5
    f12(PRE + "qfqfq", ["n_threshold"], nep=3)                                   # 6 2 episodes < 3
    f12(PRE + "fqfqfq", ["n_threshold"], nep=3)                                  # 7 3 episodes fires
    f12(PRE + "fqfq", ["n_threshold"], nep=2)                                    # 8 exactly 2
    f12(PRE + "fqqqqf", ["gap5", "f12_gap"], gap=5)                              # 9 4 quiet -> one
    f12(PRE + "fqqqqqf", ["gap5", "f12_gap"], gap=5)                             # 10 5 quiet -> two
    f12(PRE + "fqqqqqqf", ["gap5", "f12_gap"], gap=5)                            # 11 6 quiet -> two
    f12(PRE + "fqqquuf", ["gap5", "f12_gap", "unavail_quiet"], gap=5)            # 12 3q+2u = 5 -> two
    f12(PRE + "fqquuf", ["gap5", "f12_gap", "unavail_quiet"], gap=5)             # 13 4 -> one
    f12(PRE + "fqqq", ["gap5", "open_at_cutoff"], gap=5)                         # 14 quiet run 3 at T: one
    f12(PRE + "fqqqqq", ["gap5", "f12_gap"], gap=5)                              # 15 one episode, ended
    f12(PRE + "fuf", ["gap1", "unavail_quiet", "f12_unavail"])                   # 16 two
    f12(PRE + "ffuff", ["gap1", "unavail_quiet", "f12_unavail"])                 # 17 two
    f12(PRE + "uuufquu", ["unavail_edges"])                                      # 18
    f12(PRE + "qqqf", ["open_at_cutoff"])                                        # 19
    f12(PRE + "fqqq", ["episode_at_start"])                                      # 20
    f12(PRE + "qqqqq", ["no_episode"])                                           # 21
    f12(PRE + "uuuuu", ["no_available_point"])                                   # 22
    f12(PRE + "zzzzzz", ["zero_denominator_points", "no_available_point"])       # 23
    f12(PRE + "q9q9q", ["peak_tie", "f12_peak"])                                 # 24 peak 9 at earliest
    f12(PRE + "q5qq8qq8", ["peak_later_episode", "f12_peak"])                    # 25
    f12(None, ["peak_fraction"], pts=[None] * 15 + [[1000, 15000], [4321, 15000], [4321, 15000]])   # 26
    f12(PRE + "qffq" + "q" * 4 + "f" + "qqq", ["no_lookahead", "f12_lookahead"], kT=15 + 3)          # 27 T at idx 18, later points ignored
    f12(PRE + "qffq" + "q" * 4 + "f" + "qqq", ["no_lookahead", "f12_lookahead"], kT=15 + 8)          # 28 T at idx 23 includes later f
    f12(PRE + "qfq" + "fff", ["no_lookahead", "f12_lookahead"], kT=15 + 2)                           # 29 T at idx 17: one episode
    f12(PRE + "qfq" + "fff", ["no_lookahead", "f12_lookahead"], kT=15 + 5)                           # 30 extended: two
    f12(PRE + "qqf", ["sessions_separate", "f12_merge_sessions"], prior="qqqf", gap=20)                     # 31 prior session open episode
    f12(PRE + "fqq", ["sessions_separate", "f12_merge_sessions"], prior="qqfff", gap=20)                    # 32
    f12(PRE + "fq", ["insufficient_window"], el=S(899))                                              # 33
    f12(PRE + "fq", ["insufficient_window", "gate_order"], el=0)                                     # 34
    f12(PRE + "f", ["insufficient_window"], el=S(300))                                               # 35
    f12(PRE + "f", ["elapsed_exact_W", "episode_at_start"], el=S(900))                               # 36 first available point idx 15
    f12(PRE + "qq" + "f" + "q", ["off_grid"], el=S(60 * 18) + 30 * NS)                               # 37 T mid-minute: points 0..18
    f12(PRE + "qqqf" + "ffff", ["off_grid", "f12_lookahead"], el=S(60 * 17) + 59 * NS + 999999999)   # 38 floor index 17
    f12(PRE + "q2qq", ["n_param", "ratio_edge"], N=2)                                                # 39 ratio 1000*2/1000=2>=N=2 at idx 16: wait digit 2 -> ratio 2
    f12(PRE + "q4q5q", ["n_param"], N=5)                                                             # 40
    f12(PRE + "fqqf", ["gap2", "f12_gap"], gap=2)                                                    # 41 2 quiet -> two
    f12(PRE + "fqf", ["gap2", "f12_gap"], gap=2)                                                     # 42 1 quiet -> one
    f12(PRE + "fuqf", ["gap2", "unavail_quiet", "f12_unavail"], gap=2)                               # 43 u+q=2 -> two
    f12(PRE + "nfnnf", ["boundary_N", "f12_gap"])                                                    # 44 just below N quiet
    f12(PRE + "q9qq9", ["peak_tie", "f12_peak", "multi_episode"])                                    # 45
    f12(PRE + ("fq" * 6) + "q", ["many_episodes", "gap1"])                                           # 46 six episodes
    f12(PRE + "ffqffuffqqfff", ["mixed", "f12_gap"], gap=3)                                          # 47
    f12(PRE + "uzqffzfq", ["mixed", "unavail_quiet", "f12_unavail"])                                 # 48
    f12(PRE + "qqq", ["unavail_first15", "no_episode"])                                              # 49 unavailable_points 15 counted
    f12(PRE + "qnqq", ["peak_zero_episodes", "no_episode"])                                           # 50 peak 2.999 at idx 16, zero episodes
    f12(PRE + "4q4q", ["peak_zero_episodes", "no_episode", "peak_tie"], N=5)                          # 51 peak 4 earliest, zero episodes
    f12(PRE + "qqf", ["no_window_param"], prm={"N": 3, "quiet_gap": 1, "n_episodes": 1, "grid_s": 60, "window_s": 120})   # 52
    f12(PRE + "fq", ["no_window_param"], prm={"N": 3, "quiet_gap": 1, "n_episodes": 1, "window_s": 3600})                # 53
    f12(PRE + "qfq", ["default_omitted"], prm={})                                                     # 54
    assert len(R.rows) == 54, len(R.rows)
    return R.rows


if __name__ == "__main__":
    main_for("F12", "F12", build)

"""M2-9 F18 put share (30 rows) and M2-10 F19 put/call percentile (30 rows) (Q12, Q13)."""
from m2common import *


def build(rng):
    R = Rows("F18", "M2-F18")
    sess = session("2026-06-01", S(4000), 390)

    def f18(prints, tags, W=300, al=None, am=None, pending=None, noisy=False):
        ps = list(prints) + (noise(rng, 2) if noisy else [])
        prm = {"window_s": W, "at_least": al, "at_most": am}
        R.add("M2-9", "flow.md F18; matrix M2-9", "Q12", mkin(ps, sess=sess), prm, tags=tags, pending=pending)

    d = lambda s: -S(s)
    V = lambda cid, dt, q, **kw: pr(cid, dt, "1.0000", q, **kw)
    f18([V("P1", d(10), 30)], ["f18_put_only", "zero_denominator_ratio", "f18_swap"], al="1/2", noisy=True)   # 1
    f18([V("C1", d(10), 30)], ["f18_call_only", "f18_swap"], am="1/10")                                       # 2
    f18([], ["zero_denominator", "reason_closed"], al="1/2")                                                  # 3
    f18([V("P1", d(10), 30, mult=10), V("C1", d(11), 5, excl=1)], ["zero_denominator", "nonstd_counted", "cond_excl_counted"], al="1/2")  # 4
    f18([V("P1", d(10), 30), V("C1", d(11), 70), V("P1", d(12), 500, mult=10), V("C1", d(13), 900, mult=10)],
        ["nonstd_counted", "f18_swap"], al="3/10")                                                            # 5
    f18([V("P1", d(10), 20, side="unknown"), V("C1", d(11), 20, side="ask"), V("P2", d(12), 10, side="bid")],
        ["f18_unknown", "f18_inclusive"], al="3/5")                                                           # 6 share 30/50=3/5 exactly
    f18([V("P1", d(10), 50), V("C1", d(11), 50)], ["f18_inclusive", "share_edge"], al="1/2")                  # 7
    f18([V("P1", d(10), 49), V("C1", d(11), 51)], ["f18_inclusive", "share_edge"], al="1/2")                  # 8
    f18([V("P1", d(10), 51), V("C1", d(11), 49)], ["f18_inclusive", "share_edge"], al="1/2")                  # 9
    f18([V("P1", d(10), 25), V("C1", d(11), 75)], ["f18_inclusive", "share_edge"], am="1/4")                  # 10
    f18([V("P1", d(10), 26), V("C1", d(11), 74)], ["f18_inclusive", "share_edge"], am="1/4")                  # 11
    f18([V("P1", d(10), 5)], ["f18_put_only", "zero_denominator_ratio"], am="1/2")                            # 12
    f18([V("P1", d(10), 10), V("C1", d(11), 30)], ["rule_at_least_only"], al="1/2")                           # 13
    f18([V("P1", d(10), 10), V("C1", d(11), 30)], ["rule_at_most_only", "f18_inclusive"], am="1/4")          # 14
    f18([V("P1", d(10), 50), V("C1", d(11), 50)], ["rule_both"], al="3/4", am="1/4")                          # 15
    f18([V("P1", d(10), 10), V("C1", d(11), 90)], ["rule_both", "f18_inclusive"], al="3/4", am="1/4")         # 16
    f18([V("P1", d(10), 10), V("C1", d(11), 30)], ["neither_set"], pending="RULED PO-M2-AMB-6 (threshold_required), pending design ratification where design is silent")  # 17
    f18([V("P1", d(10), 10), V("C1", d(11), 30), V("P1", d(12), 100, excl=1)], ["cond_excl_counted"], am="1/2")  # 18
    f18([V("P1", -S(300), 10), V("C1", d(10), 10)], ["win_open_start"], al="1/2")                             # 19
    f18([V("P1", -S(300) - 1, 90), V("C1", d(10), 10)], ["win_open_start", "boundary_out"], al="1/2")         # 20
    f18([V("P1", 0, 10), V("C1", d(10), 10)], ["win_open_end"], al="1/2")                                     # 21
    f18([V("P1", 1, 990), V("C1", d(10), 10)], ["lookahead", "win_open_end"], al="1/2")                       # 22
    f18([V("P1", d(30), 10), V("C1", d(61), 90)], ["window_len"], W=60, al="1/2")                             # 23
    f18([V("P1", d(30), 10), V("C1", d(800), 10)], ["window_len"], W=900, al="1/2")                           # 24
    f18([V("P1", d(30), 10), V("C1", d(3500), 10), V("C1", d(3700), 900)], ["window_len"], W=3600, al="1/2")   # 25
    f18([V("P1", d(10), 7), V("C1", d(11), 3)], ["fraction", "f18_swap"], al="7/10")                          # 26 share 7/10 ratio 7/3
    f18([V("P1", d(10), 4), V("P2", d(11), 6), V("C1", d(12), 3), V("C2", d(13), 7)], ["multi_contract", "f18_inclusive"], al="1/2")  # 27
    f18([V("P1", d(10), 0), V("C1", d(11), 0)], ["size_zero", "zero_denominator"], al="1/2")                                      # 28
    f18([V("P1", d(10), 10, seq=0), V("P1", d(10), 10, seq=1), V("C1", d(10), 20, seq=2)], ["ties", "f18_inclusive"], al="1/2")  # 29
    f18([V("P1", d(10), 1), V("C1", d(11), 2)], ["fraction", "f18_swap"], am="1/3")                           # 30 1/3 exactly
    twin_s = [V("P1", d(10), 20, side="unknown"), V("C1", d(11), 20, side="ask"), V("P2", d(12), 10, side="bid"), V("C2", d(13), 10, side="unknown")]
    twin_n = [V("P1", d(10), 20), V("C1", d(11), 20), V("P2", d(12), 10), V("C2", d(13), 10)]
    f18(twin_s, ["side_twin", "f18_unknown", "f18_inclusive"], al="3/5")                               # 31
    f18(twin_n, ["side_twin", "f18_inclusive"], al="3/5")                                             # 32 equal to 31
    f18([V("P1", d(10), 5, side="unknown"), V("C1", d(11), 15, side="ask")], ["f18_unknown", "fraction"], am="1/4")  # 33 share 1/4
    assert len(R.rows) == 33, len(R.rows)

    # ------------------------------------------------------------------ F19
    R2 = Rows("F19", "M2-F19")

    def f19(put, call, ratios, tags, complete=True, nstore=20, nprior=20, incomplete_idx=None, cur_in_store=False,
            X=5, pending=None, zero_call_idx=(), old=None):
        cal, prior_ids, cur = mkcal([3] * nprior, 3)
        use = prior_ids[-nstore:] if nstore else []
        rl = list(ratios)
        if len(use) > len(rl):
            rl = [rl[0]] * (len(use) - len(rl)) + rl
        elif len(use) < len(rl):
            rl = rl[len(rl) - len(use):]
        recs = []
        for j, sid in enumerate(use):
            p, c = rl[j]
            if j in zero_call_idx:
                c = 0
            recs.append(hs(sid, 3, base=0, total=p + c, put=p, call=c,
                           complete=not (incomplete_idx is not None and j == incomplete_idx)))
        if old is not None and len(use) > 20:
            recs[0] = hs(use[0], 3, base=0, total=old[0] + old[1], put=old[0], call=old[1])
        if cur_in_store:
            recs.append(hs(cur, 3, base=0, total=10 ** 6, put=10 ** 6, call=1))
        h = hist("SYN1", "put_volume", recs)
        s = session(cur, S(23400), 3, complete=complete, put=put, call=call)
        R2.add("M2-10", "flow.md F19; matrix M2-10", "Q13", mkin(None, contracts=CONTRACTS, sess=s, cal=cal, histo=h),
               {"X": X, "K": 20}, tags=tags, pending=pending)

    ladder = [(i, 10) for i in range(1, 21)]          # ratios 1/10 .. 2
    G = ["f19", "rank"]
    f19(25, 10, ladder, G + ["above_all"])                                              # 1
    f19(20, 10, ladder, G + ["ties", "upper_share_boundary", "fires_exclusive", "rank_strict_gt"])   # 2 equal to max: 1/20 fires
    f19(20, 10, ladder[:-1] + [(20, 10)] * 1 if False else ladder[:-2] + [(20, 10), (20, 10)], G + ["ties", "upper_share_boundary", "fires_exclusive", "rank_strict_gt"])  # 3 two at top: 2/20
    f19(1, 20, ladder, G + ["below_all"])                                               # 4 0.05
    f19(105, 100, ladder, G + ["middle"])                                               # 5 1.05
    f19(10, 10, [(10, 10)] * 20, G + ["constant_history", "fires_exclusive", "zscore_absent"])        # 6
    f19(11, 10, [(10, 10)] * 20, G + ["constant_history", "fires_exclusive", "zscore_absent"])        # 7
    f19(10, 10, ladder, G + ["gate_history", "zero_call_prior"], zero_call_idx=(4,))    # 8 19 usable
    f19(10, 10, ladder, G + ["gate_history", "zero_call_prior"], zero_call_idx=(0, 19))  # 9
    f19(30, 10, ladder, G + ["zero_call_prior", "k21"], nprior=21, nstore=21, zero_call_idx=(0,), old=(5, 0))  # 10 oldest outside window
    f19(10, 10, ladder, G + ["zero_call_prior", "f19_zero_counted"], zero_call_idx=(2,), nprior=21, nstore=21)  # 11 zero call inside window -> insufficient
    f19(10, 10, ladder, G + ["gate_history", "history_count"], nstore=19)               # 12
    f19(10, 10, ladder, G + ["history_count"])                                          # 13 20 usable available
    f19(10, 10, ladder, G + ["gate_history", "incomplete_session"], incomplete_idx=9)   # 14
    f19(10, 10, ladder, G + ["gate_history", "nothing_stored"], nstore=0)               # 15
    f19(10, 10, ladder, G + ["session_not_complete"], complete=False)                   # 16
    f19(10, 10, ladder, G + ["gate_order", "gate_history", "session_not_complete"], complete=False, nstore=19)  # 17
    f19(10, 0, ladder, G + ["zero_denominator"])                                        # 18
    f19(0, 10, ladder, G + ["zero_numerator", "rank_strict_gt"])                        # 19 ratio 0
    f19(10, 0, [(10, 10)] * 20, G + ["zero_denominator", "constant_history"])             # 20
    f19(25, 10, ladder, G + ["today_excluded"], cur_in_store=True)                      # 21
    f19(25, 10, ladder, G + ["k21", "history_count"], nprior=21, nstore=21, old=(500, 1))  # 22
    f19(7, 3, [(i, 7) for i in range(1, 21)], G + ["fraction"])                         # 23 7/3 vs i/7
    f19(21, 10, ladder, G + ["session_not_complete"], complete=False)                # 24
    f19(18, 10, ladder, G + ["upper_share_boundary", "fires_exclusive"], X=10)          # 25 18/10: count >=1.8 -> 1.8,1.9,2 =3? no: 18..20 -> 3/20
    f19(19, 10, ladder, G + ["upper_share_boundary", "fires_exclusive"], X=10)          # 26 2/20 fires
    f19(0, 10, [(0, 10)] * 10 + [(10, 10)] * 10, G + ["zero_put_prior", "rank_strict_gt"])  # 27 prior ratio 0 valid
    f19(10 ** 6, 0, ladder, G + ["zero_denominator", "big_volume"])                                   # 28
    f19(10, 0, ladder, G + ["gate_order", "gate_history", "zero_denominator"], nstore=19)   # 29
    f19(10, 0, ladder, G + ["gate_order", "session_not_complete", "zero_denominator"], complete=False)  # 30
    f19(10, 10, ladder, G + ["zero_call_prior", "f19_zero_counted", "gate_history"], zero_call_idx=(19,))    # 31
    R2.add("M2-10", "flow.md F19; matrix M2-10", "Q13", mkin(None, contracts=CONTRACTS, sess=session(R2.rows[12]["inputs"]["session"]["session_id"], S(23400), 3, complete=True, put=25, call=10),
           cal=R2.rows[12]["inputs"]["calendar"], histo=R2.rows[12]["inputs"]["history"]), {}, tags=G + ["default_omitted"])   # 32 X and K omitted
    f19(10, 10, ladder, G + ["gate_order", "gate_history", "session_not_complete"], complete=False, incomplete_idx=3)   # 33
    assert len(R2.rows) == 33, len(R2.rows)
    return R.rows + R2.rows


if __name__ == "__main__":
    main_for("F18F19", "F18,F19", build)

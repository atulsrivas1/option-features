"""Indexed view of one (Snapshot, Request) pair plus digest, visibility and evidence helpers."""
from option_feature_contracts.variants1.canonical import record_digest, fail

DEP_ORDER_KEY = lambda d: (d["record_type"], d["record_id"], d["use"])


class Ctx:
    def __init__(self, snapshot, request, cohort_sha256, producer_admission=None, input_checkpoint_sha256=None):
        self.snap = snapshot
        self.req = request
        self.cohort = cohort_sha256
        self.admission = producer_admission
        self.input_checkpoint = input_checkpoint_sha256
        self.K = request["knowledge_K_ns"]
        self.cursor = {c["stream_id"]: c["position"] for c in request["cut_cursors"]}
        self._dig = {}
        s = snapshot

        def idx(rows, key):
            out = {}
            for r in rows:
                out.setdefault(r[key], r)
            return out

        self.bindings = idx(s["bindings"], "binding_id")
        self.scopes = idx(s["scopes"], "scope_id")
        self.defs = idx(s["definitions"], "definition_id")
        self.refs = idx(s["references"], "reference_id")
        self.execs = idx(s["executions"], "revision_id")
        self.quotes = idx(s["quotes"], "revision_id")
        self.pairings = idx(s["pairings"], "pairing_id")
        self.controls = idx(s["controls"], "control_id")
        self.supplied = idx(s["supplied_premiums"], "premium_id")
        self.dailies = idx(s["daily_observations"], "observation_id")
        self.slots = idx(s["baseline_slots"], "slot_id")
        self.bpolicies = idx(s["bucket_policies"], "policy_id")
        self.frames = idx(s["session_frames"], "frame_id")
        self.targets = idx(s["activity_targets"], "target_id")
        self.bcerts = idx(s["bucket_certificates"], "certificate_id")
        self.dcerts = idx(s["daily_activity_certificates"], "certificate_id")
        self.policies = idx(request["policies"], "policy_id")
        self.ops = {o["op_id"]: o for o in request["operations"]}
        self.roots = {}
        for e in s["executions"]:
            self.roots.setdefault(e["root_id"], []).append(e)
        self.qroots = {}
        for q in s["quotes"]:
            self.qroots.setdefault(q["quote_id"], []).append(q)

    # ---- digests -------------------------------------------------------
    def rd(self, rtype, rec):
        key = (rtype, id(rec))
        h = self._dig.get(key)
        if h is None:
            h = record_digest(rtype, rec)
            self._dig[key] = (h, rec)
            return h
        return h[0]

    def policy_hash(self, policy_id):
        return self.rd("variant_Policy", self.policies[policy_id])

    # ---- visibility ----------------------------------------------------
    def vis_K(self, stamp):
        pos = self.cursor.get(stamp["stream_id"])
        return pos is not None and stamp["known_at_ns"] <= self.K and stamp["position"] <= pos

    def vis_A(self, stamp, a_ns):
        pos = self.cursor.get(stamp["stream_id"])
        return pos is not None and stamp["known_at_ns"] <= a_ns and stamp["position"] <= pos and stamp["known_at_ns"] <= self.K

    # ---- chains ----------------------------------------------------------
    def chain(self, root_id):
        """Execution revisions of a root in chain order (new first)."""
        revs = self.roots.get(root_id, [])
        by_target = {}
        for r in revs:
            by_target.setdefault(r["target_revision_id"], []).append(r)
        out = []
        cur = by_target.get(None, [])
        seen = set()
        while cur:
            r = cur[0]
            if r["revision_id"] in seen:
                break
            seen.add(r["revision_id"])
            out.append(r)
            cur = by_target.get(r["revision_id"], [])
        if len(out) != len(revs):  # malformed graph: fall back to stream position order
            out = sorted(revs, key=lambda r: (r["stamp"]["position"], r["revision_id"]))
        return out

    def k_selected(self, root_id):
        """Latest K/cursor-visible revision of a root (chain prefix), or None."""
        sel = None
        for r in self.chain(root_id):
            if self.vis_K(r["stamp"]):
                sel = r
            else:
                break
        return sel

    def a_selected(self, root_id, a_ns):
        sel = None
        for r in self.chain(root_id):
            if self.vis_A(r["stamp"], a_ns):
                sel = r
            else:
                break
        return sel

    def new_rev(self, root_id):
        for r in self.roots.get(root_id, []):
            if r["kind"] == "new":
                return r
        return None


def dep(rtype, rid, rhash, use, known):
    return {"known_at_ns": known, "record_id": rid, "record_sha256": rhash, "record_type": rtype, "use": use}


class Deps:
    """Accumulates unique dependencies; available_at is the maximum known_at (0 if none)."""

    def __init__(self):
        self.d = {}

    def add(self, rtype, rid, rhash, use, known):
        self.d[(rtype, rid, use)] = dep(rtype, rid, rhash, use, known)
        return self

    def update(self, other):
        self.d.update(other.d)
        return self

    def sorted(self):
        return [self.d[k] for k in sorted(self.d)]

    def available_at(self):
        return max((v["known_at_ns"] for v in self.d.values()), default=0)


def make_evidence(deps, member_ids=(), member_revision_ids=(), unknown_sign_ids=(), unknown_reference_ids=(),
                  excluded_ids=(), control_ids=(), capture_complete=False, context_complete=False,
                  eligibility=None, bucket_domain_evidence=()):
    return {
        "available_at_ns": deps.available_at(),
        "bucket_domain_evidence": list(bucket_domain_evidence),
        "capture_complete": capture_complete,
        "context_complete": context_complete,
        "control_ids": sorted(set(control_ids)),
        "dependencies": deps.sorted(),
        "eligibility": eligibility,
        "excluded_ids": sorted(set(excluded_ids)),
        "member_ids": list(member_ids),
        "member_revision_ids": list(member_revision_ids),
        "unknown_reference_ids": sorted(set(unknown_reference_ids)),
        "unknown_sign_ids": sorted(set(unknown_sign_ids)),
    }

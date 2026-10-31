"""M3a history rank outputs (story S08): M3A-1 (V1), M3A-2 (V3), M3A-8 (V9). STUB: every call raises
NotImplementedError until the implementation commit (failing-first)."""


def rank_v1(store, underlying, session, evaluation_ns, now, params=None, upstream_reason=None,
            labels=("exact-model",), cutoff_ns=None):
    raise NotImplementedError


def rank_v3(store, underlying, session, evaluation_ns, now, params=None, upstream_reason=None,
            labels=("exact-model",), cutoff_ns=None):
    raise NotImplementedError


def rank_v9(store, underlying, session, evaluation_ns, put25_iv, call25_iv, params=None, upstream_reason=None,
            labels=("exact-model",), cutoff_ns=None):
    raise NotImplementedError

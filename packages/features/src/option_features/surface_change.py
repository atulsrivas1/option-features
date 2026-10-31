"""M3a story S07: change outputs against a prior reading, V4 (M3A-3), V7 (M3A-6), V10 (M3A-9). STUB (failing-first)."""

OUTPUT_V4, OUTPUT_V7, OUTPUT_V10 = "M3A-3", "M3A-6", "M3A-9"


def iv_change(frame, floats, cutoff_ns, params):
    raise NotImplementedError


def gap_change(frame, floats, cutoff_ns, params, store=None, series_id=None, session_id=None):
    raise NotImplementedError


def skew_change(frame, floats, cutoff_ns, params, store=None, series_id=None, session_id=None):
    raise NotImplementedError

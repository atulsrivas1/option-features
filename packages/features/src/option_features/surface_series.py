"""M3a story S10: series builder M3A-12 (STUB for the failing-first commit)."""


def series_id(underlying, lane, metric):
    raise NotImplementedError


def scalar_units(floats, floats_fwd=None):
    raise NotImplementedError


def grid_units(values):
    raise NotImplementedError


def build_records(underlying, lane, session_id, close_floats, close_floats_fwd=None, minute_floats=None):
    raise NotImplementedError


def append_records(store, records, lane="stock"):
    raise NotImplementedError

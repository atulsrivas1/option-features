"""M3a common (story S01) - STUB. Every function raises NotImplementedError; constants are empty."""
SURFACE_REASONS = ()
CONTRACT_REASONS = ()
CODES = ()
STATUSES = ()
KEY_ORDER = ()
DEFAULTS = {}
UNITS = 0


def round_units(x):
    raise NotImplementedError


def round_scaled_units(x, scale):
    raise NotImplementedError


def units_text(u):
    raise NotImplementedError


def round_text(x):
    raise NotImplementedError


def skew_units(put, call):
    raise NotImplementedError


def skew_points_units(put, call):
    raise NotImplementedError


def ratio_text(n, d):
    raise NotImplementedError


def sort_labels(labels):
    raise NotImplementedError


def params_echo(params, names):
    raise NotImplementedError


class Result:
    def __init__(self, *a, **k):
        raise NotImplementedError


def canonical_line(result):
    raise NotImplementedError


def canonical_bytes(results):
    raise NotImplementedError

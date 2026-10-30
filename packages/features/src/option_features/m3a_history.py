"""M3a history reads (story S02): `scalar_baseline`, `same_minute_column` over the M2 store (stub)."""

STORE_BUDGET_BYTES = 768 * 1024 * 1024
STORE_HARD_BYTES = 1024 * 1024 * 1024


class HistoryRead:
    __slots__ = ("status", "reason", "code", "value")


def scalar_baseline(store, series_id, metric, as_of, min_sessions=20, max_sessions=252, lane="stock",
                    delta_convention=None, x=None, window_s=0):
    raise NotImplementedError


def same_minute_column(store, series_id, metric, as_of, minute, min_sessions=20, max_sessions=252, lane="stock",
                       delta_convention=None, x=None, window_s=0):
    raise NotImplementedError


def grid_store_bytes(names, k, grid, copies):
    raise NotImplementedError


def scalar_store_bytes(names, series, k):
    raise NotImplementedError

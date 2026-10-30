"""M3a structural validation wrappers (story S09). Failing-first stub: every function raises NotImplementedError."""

REQUEST_LIST = ()
VIEW_READ_LIST = ()


def validate_request(output_id, contracts, spot, rate, dividend_yield, cutoff_ns, params, validate="scanned"):
    raise NotImplementedError


def validate_view_read(calendar, as_of, form, min_sessions, max_sessions, x=None, minute=None, series_id=None,
                       delta_convention="spot"):
    raise NotImplementedError


def store_call(fn, *args, **kwargs):
    raise NotImplementedError


def m1_error_code(exc):
    raise NotImplementedError

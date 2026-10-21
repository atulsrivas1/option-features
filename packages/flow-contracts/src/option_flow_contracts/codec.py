"""Bounded, closed canonical JSON encoding; no I/O or dynamic registrations."""
from dataclasses import fields
from decimal import Decimal
from hashlib import sha256
from math import gcd
import json
import re
import types
import unicodedata
from typing import get_args, get_origin

from . import records as r

_CLASSES = (
    r.FlowRational, r.FlowLimits, r.FlowBinding, r.FlowReference,
    r.FlowExecution, r.FlowQuote, r.FlowGroup, r.FlowPopulation,
    r.FlowContextCertificate, r.FlowBaseline, r.FlowCursor, r.FlowSnapshot,
    r.FlowPolicy, r.FlowBaselineTarget, r.FlowRequest, r.FlowCoverage,
    r.FlowSignWitness, r.FlowOperand, r.FlowPartitionWeight, r.FlowExcluded,
    r.FlowCluster, r.FlowEvidence, r.FlowResult, r.FlowCheckpoint,
    r.FlowPublication,
)
REGISTRY = {
    re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower(): cls
    for cls in _CLASSES
}
REGISTRY['flow_results'] = tuple
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z', re.ASCII)
_HASH = re.compile(r'[0-9a-f]{64}\Z', re.ASCII)
_INTEGER = re.compile(r'0|-?[1-9][0-9]*\Z', re.ASCII)
_DECIMAL = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?\Z', re.ASCII)
_VERSIONS = {
    r.FlowSnapshot: 'option-flow-canonical1', r.FlowPolicy: 'r26-flow-policy1',
    r.FlowRequest: 'option-flow-request1', r.FlowResult: 'option-flow-result1',
    r.FlowCheckpoint: 'option-flow-checkpoint1',
    r.FlowPublication: 'option-flow-generation1',
}
SIGN_REASONS = frozenset(('quote_above_midpoint','quote_below_midpoint','quote_midpoint',
    'quote_locked','quote_crossed','quote_missing','quote_one_sided','quote_stale','quote_future',
    'quote_order_unknown','tick_up','tick_down','tick_carried','tick_initial_unknown',
    'tick_seed_unavailable','observed_buy','observed_sell','observed_unknown','observed_missing','observed_future'))
QUALITY_FLAGS = frozenset(('partial_sign_coverage','partial_dte_coverage','partial_otm_coverage',
                          'supplied_baseline','proxy_direction','corrected_history','complete_empty'))
RESULT_REASONS = frozenset(('ok','zero_denominator','zero_mad','insufficient_pairs','zero_variance',
    'incomplete_population','missing_baseline','incomplete_baseline','insufficient_history',
    'missing_dte_reference','missing_spot_reference','missing_venue_reference','future_reference',
    'stale_reference','incompatible_equity_operand','missing_equity_operand','unsupported_profile',
    'unsupported_deliverable','equity_integration_unqualified'))
DIAGNOSTICS = SIGN_REASONS | QUALITY_FLAGS | RESULT_REASONS | {'outside_spread','excluded_quote','incomplete_context'}


def fail(code, path):
    raise r.FlowValidationError(code, path)


def decimal_text(value):
    """Context-independent exact decimal rendering using its finite tuple."""
    if type(value) is not Decimal:
        fail('type_mismatch', '')
    if not value.is_finite():
        fail('invalid_scalar', '')
    sign, digits, exponent = value.as_tuple()
    if not any(digits):
        return '0'
    # Strip representational zeros before imposing value precision/scale.
    # Decimal.normalize() would obey the ambient context and may round.
    while digits[-1] == 0:
        digits = digits[:-1]
        exponent += 1
    if len(digits) > 38 or exponent < -18 or exponent > 38:
        fail('resource_limit', '')
    digits = ''.join(map(str, digits))
    if exponent >= 0:
        result = digits + '0' * exponent
    elif len(digits) + exponent > 0:
        result = digits[:exponent] + '.' + digits[exponent:]
    else:
        result = '0.' + '0' * (-exponent - len(digits)) + digits
    if '.' in result:
        result = result.rstrip('0').rstrip('.')
    return ('-' if sign else '') + result


def _tuple_key(value):
    cls = type(value)
    if cls is r.FlowResult:
        return value.group_id, value.output_id, value.cluster_id or ''
    if cls is r.FlowExecution:
        return value.execution_id, value.revision_id
    if cls is r.FlowQuote:
        return value.quote_id, value.revision_id
    if cls is r.FlowSignWitness:
        return value.execution_id, value.revision_id
    if cls is r.FlowPartitionWeight:
        return value.partition_kind, value.partition_id
    if cls is r.FlowExcluded:
        return value.execution_id, value.revision_id, value.reason
    for name in ('binding_id', 'reference_id', 'group_id', 'population_id',
                 'certificate_id', 'baseline_id', 'stream_id', 'name'):
        if hasattr(value, name):
            return getattr(value, name)
    return value


_ORDERED = {'slot_ids', 'execution_ids', 'execution_revision_ids',
            'active_execution_ids', 'active_revision_ids', 'baseline_slot_ids',
            'baseline_record_sha256s'}


def _payload(value, field_name=''):
    cls = type(value)
    if cls in _CLASSES:
        return {f.name: (str(getattr(value, f.name))
                        if cls is r.FlowRational or
                        (cls is r.FlowExecution and f.name == 'quantity' and
                         getattr(value, f.name) is not None)
                        else _payload(getattr(value, f.name), f.name))
                for f in fields(value)}
    if cls is Decimal:
        return decimal_text(value)
    if cls is tuple:
        values = value if field_name in _ORDERED else sorted(value, key=_tuple_key)
        return [_payload(item) for item in values]
    return value


def flow_to_payload(value):
    _validate(value, r.FLOW_LIMITS, '', [0])
    _semantic(value)
    return _payload(value)


def _semantic(value):
    # Closed lazy dispatch avoids an import cycle without extensible callbacks.
    from .validation import (flow_validate_snapshot, flow_validate_request,
                             flow_validate_results, validate_checkpoint,
                             validate_publication)
    cls=type(value)
    if cls is r.FlowSnapshot:flow_validate_snapshot(value)
    elif cls is r.FlowRequest:flow_validate_request(value)
    elif cls is r.FlowResult:flow_validate_results((value,))
    elif cls is tuple:flow_validate_results(value)
    elif cls is r.FlowCheckpoint:validate_checkpoint(value)
    elif cls is r.FlowPublication:validate_publication(value)


def _json(payload):
    return json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def flow_canonical_bytes(value):
    result = _json(flow_to_payload(value))
    if len(result) > r.FLOW_LIMITS.max_wire_bytes:
        fail('resource_limit', '')
    return result


def _digest(domain, record_type, value):
    _registered(record_type, value)
    return sha256((domain + '\n' + record_type + '\n').encode('utf-8') +
                  flow_canonical_bytes(value)).hexdigest()


def flow_content_digest(record_type, value):
    return _digest('option-flow-json1', record_type, value)


def flow_record_digest(record_type, value):
    return _digest('option-flow-record1', record_type, value)


def _registered(record_type, value=None):
    if type(record_type) is not str or record_type not in REGISTRY:
        fail('unsupported_schema', '/record_type')
    if value is not None and type(value) is not REGISTRY[record_type]:
        fail('type_mismatch', '/payload')


def _shape(value, expected, path, wire, limits, count):
    if type(value) is _NonIntegerToken:
        fail('type_mismatch', path)
    if type(value) is _OversizedIntegerToken:
        fail('resource_limit', path)
    origin, args = get_origin(expected), get_args(expected)
    if origin is types.UnionType:
        if value is None and type(None) in args:
            return None
        expected = next(a for a in args if a is not type(None))
        origin, args = get_origin(expected), get_args(expected)
    if origin is tuple:
        if type(value) is not (list if wire else tuple):
            fail('type_mismatch', path)
        if len(value) > limits.max_records:
            fail('resource_limit', path)
        return tuple(_shape(item, args[0], f'{path}/{i}', wire, limits, count)
                     for i, item in enumerate(value))
    if expected in _CLASSES:
        if wire:
            if type(value) is not dict:
                fail('type_mismatch', path)
            if set(value) != {f.name for f in fields(expected)}:
                fail('field_set', path)
            count[0] += 1
            if count[0] > limits.max_records:
                fail('resource_limit', path)
            kwargs = {}
            for f in fields(expected):
                raw = value[f.name]
                ptr = path + '/' + f.name
                if expected is r.FlowRational or (expected is r.FlowExecution
                                                and f.name == 'quantity' and raw is not None):
                    cap = 256 if expected is r.FlowRational else 128
                    if type(raw) is not str:
                        fail('type_mismatch', ptr)
                    if len(raw.lstrip('-')) > cap:
                        fail('resource_limit', ptr)
                    if _INTEGER.fullmatch(raw) is None:
                        fail('noncanonical', ptr)
                    raw = int(raw)
                    kwargs[f.name] = raw
                else:
                    kwargs[f.name] = _shape(raw, f.type, ptr, True, limits, count)
            return expected(**kwargs)
        if type(value) is not expected:
            fail('type_mismatch', path)
        _validate(value, limits, path, count)
        return value
    if expected is Decimal and wire:
        if type(value) is not str:
            fail('type_mismatch', path)
        if len(value) > 80:
            fail('resource_limit', path)
        if value == '-0' or _DECIMAL.fullmatch(value) is None:
            if re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?', value):
                fail('noncanonical', path)
            fail('invalid_scalar', path)
        return Decimal(value)
    if type(value) is not expected:
        fail('type_mismatch', path)
    return value


def _shape_first(value, expected, path, count, limits):
    """Finish global stage3 shape admission before any stage4 scalar bounds."""
    origin,args=get_origin(expected),get_args(expected)
    if origin is types.UnionType:
        if value is None and type(None) in args:return
        expected=next(a for a in args if a is not type(None))
        origin,args=get_origin(expected),get_args(expected)
    if origin is tuple:
        if type(value) is not tuple:fail('type_mismatch',path)
        if len(value)>limits.max_records:fail('resource_limit',path)
        for index,item in enumerate(value):
            _shape_first(item,args[0],f'{path}/{index}',count,limits)
    elif expected in _CLASSES:
        if type(value) is not expected:fail('type_mismatch',path)
        count[0]+=1
        if count[0]>limits.max_records:fail('resource_limit',path)
        for field in fields(expected):
            _shape_first(getattr(value,field.name),field.type,path+'/'+field.name,count,limits)
    elif type(value) is not expected:
        fail('type_mismatch',path)


def _validate(value, limits, path, count):
    cls = type(value)
    _shape_first(value,tuple[r.FlowResult,...] if cls is tuple else cls,path,[0],limits)
    if cls is tuple:
        if len(value) > limits.max_result_rows:
            fail('resource_limit', path)
        for i, row in enumerate(value):
            if type(row) is not r.FlowResult:
                fail('type_mismatch', f'{path}/{i}')
            _validate(row, limits, f'{path}/{i}', count)
        return
    if cls not in _CLASSES:
        fail('type_mismatch', path)
    count[0] += 1
    if count[0] > limits.max_records:
        fail('resource_limit', path)
    for f in fields(value):
        item, ptr = getattr(value, f.name), path + '/' + f.name
        _shape(item, f.type, ptr, False, limits, count)
        if item is None:
            continue
        if type(item) is str:
            if f.name.endswith('sha256') or f.name == 'cluster_id':
                if _HASH.fullmatch(item) is None:
                    fail('invalid_scalar', ptr)
            elif f.name == 'currency':
                if re.fullmatch('[A-Z]{3}', item, re.ASCII) is None:
                    fail('invalid_scalar', ptr)
            elif f.name == 'rights_reference':
                if (not item or len(item.encode('utf-8', errors='surrogatepass')) > 1024
                    or unicodedata.normalize('NFC', item) != item
                    or any(unicodedata.category(c) in {'Cc', 'Cf', 'Cs'} for c in item)):
                    fail('invalid_scalar', ptr)
            elif _ID.fullmatch(item) is None:
                fail('invalid_scalar', ptr)
        if type(item) is int:
            cap = 256 if cls is r.FlowRational else 128 if f.name == 'quantity' else 19
            # Bound typed arbitrary-size integers before decimal string conversion.
            # Python's configurable int-to-string ceiling is not our error API.
            if abs(item) >= 10**cap:
                fail('resource_limit', ptr)
            if cls is not r.FlowRational and f.name != 'quantity' and not 0 <= item <= 2**63 - 1:
                fail('invalid_scalar', ptr)
        if type(item) is Decimal:
            try:
                rendered = decimal_text(item)
            except r.FlowValidationError as error:
                fail(error.code, ptr)
            if item < 0 or item >= Decimal('1e38'):
                fail('invalid_scalar', ptr)
        if type(item) is tuple and get_origin(f.type) is tuple and get_args(f.type)[0] is str:
            for index, member in enumerate(item):
                pattern = _HASH if 'sha256' in f.name else _ID
                if pattern.fullmatch(member) is None:
                    fail('invalid_scalar', f'{ptr}/{index}')
            # Paired revision arrays need not have unique revisions across roots.
            if f.name not in ('execution_revision_ids','active_revision_ids') and len(set(item)) != len(item):
                fail('identity_conflict', ptr)
    _local(value, path, limits)


def _local(v, p, limits):
    cls = type(v)
    def require(test, field, code='invalid_scalar'):
        if not test:
            fail(code, p + '/' + field)
    def enum(field, choices):
        require(getattr(v, field) in choices, field)
    if cls in _VERSIONS:
        require(v.schema_version == _VERSIONS[cls], 'schema_version', 'unsupported_schema')
    if hasattr(v, 'formula_version'):
        require(v.formula_version == 'option-flow-formulas1', 'formula_version', 'identity_mismatch')
    if hasattr(v, 'window_start_ns'):
        require(v.window_start_ns < v.window_end_ns, 'window_end_ns')
    for name in ('expiry_ordinal', 'civil_ordinal', 'session_ordinal', 'target_session_ordinal'):
        if hasattr(v, name) and getattr(v, name) is not None:
            require(1 <= getattr(v, name) <= 3652059, name)
    if cls is r.FlowRational:
        require(v.denominator > 0, 'denominator')
        require(gcd(abs(v.numerator), v.denominator) == 1, 'numerator')
    elif cls is r.FlowLimits:
        for field in fields(v):
            require(0 < getattr(v, field.name) <= getattr(r.FLOW_LIMITS, field.name), field.name, 'resource_limit')
    elif cls is r.FlowBinding:
        enum('provenance_mode', ('synthetic', 'licensed', 'public_permitted'))
    elif cls is r.FlowReference:
        enum('right', ('call', 'put'))
        require(v.strike > 0, 'strike'); require(v.multiplier > 0, 'multiplier')
        require(v.effective_to_ns is None or v.effective_to_ns > v.effective_from_ns, 'effective_to_ns')
        for names in (('civil_ordinal','civil_instant_ns','civil_known_at_ns','calendar_id','calendar_revision'),
                      ('spot','spot_event_ns','spot_known_at_ns','spot_stream_id','spot_position')):
            require(all(getattr(v, n) is None for n in names) or all(getattr(v, n) is not None for n in names), names[0])
        require(v.spot is None or v.spot > 0, 'spot')
    elif cls in (r.FlowExecution, r.FlowQuote):
        enum('kind', ('new', 'cancel', 'replace')); enum('condition', ('regular', 'excluded'))
        id_field = 'execution_id' if cls is r.FlowExecution else 'quote_id'
        target = getattr(v, 'target_' + id_field)
        require((target is None and v.target_revision_id is None) if v.kind == 'new'
                else (target == getattr(v, id_field) and v.target_revision_id is not None), 'target_' + id_field)
        if cls is r.FlowExecution:
            enum('observed_side', ('buy', 'sell', 'unknown'))
            require(v.signing_boundary_ns >= v.event_ns, 'signing_boundary_ns')
            if v.kind == 'new':
                require(v.known_at_ns <= v.signing_boundary_ns, 'known_at_ns')
            require((v.observed_side_semantics_id is None) == (v.observed_side_known_at_ns is None), 'observed_side_semantics_id')
            require(v.observed_side_semantics_id is not None or v.observed_side == 'unknown', 'observed_side')
            if v.kind == 'cancel':
                require(v.price is None and v.quantity is None and v.condition == 'excluded' and v.observed_side == 'unknown', 'price')
            else:
                require(v.price is not None, 'price'); require(v.quantity is not None and v.quantity > 0, 'quantity')
        elif v.kind == 'cancel':
            require(v.bid is None and v.ask is None and v.condition == 'excluded', 'bid')
    elif cls is r.FlowGroup:
        enum('kind', ('underlying', 'contract', 'right', 'expiry'))
        require(bool(v.contract_ids), 'contract_ids')
        require(v.kind != 'contract' or len(v.contract_ids) == 1, 'contract_ids')
        require((v.right in ('call', 'put') and v.expiry_ordinal is None) if v.kind == 'right'
                else (v.expiry_ordinal is not None and v.right is None) if v.kind == 'expiry'
                else v.right is None and v.expiry_ordinal is None, 'right')
    elif cls is r.FlowPolicy:
        require(v.temporal_profile == 'option-origin-context1', 'temporal_profile', 'identity_mismatch')
        enum('signing_profile', ('option-quote-midpoint1', 'option-tick1', 'option-observed-side1'))
        require(v.short_dte_max_days <= 3652058, 'short_dte_max_days')
        require(1 <= v.minimum_matched_prior_windows <= 32, 'minimum_matched_prior_windows')
    elif cls is r.FlowRequest:
        require(v.window_end_ns <= v.knowledge_cutoff_ns, 'knowledge_cutoff_ns')
        require(bool(v.group_ids), 'group_ids'); require(bool(v.output_ids), 'output_ids')
        require(len(v.group_ids) <= limits.max_groups, 'group_ids', 'resource_limit')
        require(len(v.output_ids) <= limits.max_outputs, 'output_ids', 'resource_limit')
    elif cls is r.FlowBaselineTarget:
        require(1 <= len(v.slot_ids) <= 32, 'slot_ids', 'resource_limit')
    elif cls is r.FlowContextCertificate:
        enum('kind', ('execution_prefix', 'quote_prefix'))
    elif cls is r.FlowSignWitness:
        enum('sign', ('buy','sell','unknown'))
        enum('method', ('option-quote-midpoint1','option-tick1','option-observed-side1'))
        enum('reason', SIGN_REASONS)
        require(set(v.diagnostics) <= SIGN_REASONS | {'outside_spread','excluded_quote','incomplete_context'}, 'diagnostics')
        require((v.quote_id is None) == (v.quote_revision_id is None),'quote_id')
        require((v.predecessor_execution_id is None) == (v.predecessor_revision_id is None),'predecessor_execution_id')
        require(v.method=='option-quote-midpoint1' or v.quote_id is None,'quote_id')
        require(v.method=='option-tick1' or v.predecessor_execution_id is None,'predecessor_execution_id')
    elif cls is r.FlowExcluded:
        enum('reason', ('cancelled','excluded','future_known','outside_window'))
    elif cls is r.FlowOperand:
        enum('name', ('count','contracts','share_equivalent','premium','buy_premium','sell_premium',
                     'unknown_premium','signed_premium','total_premium','call_premium','put_premium',
                     'numerator','denominator','median','mad','mad_scale','current','baseline_count',
                     'known_reference_premium','qualified_premium','cluster_premium','cluster_contracts',
                     'cluster_count','cluster_span','known_venue_count','unknown_venue_count'))
    elif cls is r.FlowPartitionWeight:
        enum('partition_kind', ('contract','expiry'))
        require(v.premium.numerator >= 0,'premium')
    elif cls is r.FlowCluster:
        require(v.profile=='option-quote-cluster1','profile','identity_mismatch')
        enum('sign', ('buy','sell'))
        require(bool(v.execution_ids) and len(v.execution_ids)==len(v.execution_revision_ids),'execution_ids')
        require(v.first_event_ns<=v.last_event_ns,'last_event_ns')
    elif cls is r.FlowEvidence:
        require(len(v.active_execution_ids)==len(v.active_revision_ids),'active_revision_ids')
        require(set(v.diagnostics)<=DIAGNOSTICS,'diagnostics')
        require(len({o.name for o in v.operands})==len(v.operands),'operands','identity_conflict')
    elif cls is r.FlowResult:
        require(v.origin=='computed','origin')
        require(v.temporal_profile=='option-origin-context1','temporal_profile','identity_mismatch')
        require(v.contracts_package_version=='0.1.0a1','contracts_package_version','identity_mismatch')
        require(v.calculation_package_version=='0.1.0a1','calculation_package_version','identity_mismatch')
        require(set(v.quality_flags)<=QUALITY_FLAGS,'quality_flags')
        require((v.numerator is None)==(v.denominator is None),'denominator','identity_mismatch')


def flow_from_payload(record_type, payload, limits=r.FLOW_LIMITS):
    _registered(record_type)
    _validate(limits, r.FLOW_LIMITS, '/limits', [0])
    if record_type == 'flow_results':
        value = _shape(payload, tuple[r.FlowResult, ...], '/payload', True, limits, [0])
    else:
        value = _shape(payload, REGISTRY[record_type], '/payload', True, limits, [0])
    _validate(value, limits, '/payload', [0])
    _semantic(value)
    return value


def encode_flow_record(record_type, value):
    _registered(record_type, value)
    payload = flow_to_payload(value)
    envelope = {'schema_version': 'option-flow-json1', 'record_type': record_type,
                'content_sha256': flow_content_digest(record_type, value), 'payload': payload}
    data = _json(envelope)
    if len(data) > r.FLOW_LIMITS.max_wire_bytes:
        fail('resource_limit', '')
    return data


class _Pairs(list):
    pass


class _NonIntegerToken(str):
    pass


class _OversizedIntegerToken(str):
    pass


def _unpair(value, path=''):
    if type(value) is _Pairs:
        result = {}
        for key, child in value:
            pointer = path + '/' + key.replace('~', '~0').replace('/', '~1')
            if key in result:
                fail('field_set', pointer)
            result[key] = _unpair(child, pointer)
        return result
    if type(value) is list:
        return [_unpair(child, f'{path}/{i}') for i, child in enumerate(value)]
    return value


def decode_flow_record(record_type, data, limits=r.FLOW_LIMITS):
    _registered(record_type)
    _validate(limits, r.FLOW_LIMITS, '/limits', [0])
    if type(data) is not bytes:
        fail('type_mismatch', '')
    if len(data) > limits.max_wire_bytes:
        fail('resource_limit', '')
    try:
        text = data.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        fail('invalid_utf8', '')
    depth = 0; quoted = False; escaped = False
    for char in text:
        if quoted:
            if escaped: escaped = False
            elif char == '\\': escaped = True
            elif char == '"': quoted = False
        elif char == '"': quoted = True
        elif char in '[{':
            depth += 1
            if depth > 32: fail('resource_limit', '')
        elif char in ']}': depth -= 1
    def parse_int(token):
        if len(token.lstrip('-')) > 128:
            return _OversizedIntegerToken(token)
        return int(token)
    try:
        envelope = _unpair(json.loads(text, object_pairs_hook=_Pairs,
                                     parse_int=parse_int, parse_float=_NonIntegerToken,
                                     parse_constant=_NonIntegerToken))
    except (json.JSONDecodeError, RecursionError):
        fail('invalid_json', '')
    if type(envelope) is not dict:
        fail('type_mismatch', '')
    if set(envelope) != {'schema_version','record_type','content_sha256','payload'}:
        fail('field_set', '')
    if envelope['schema_version'] != 'option-flow-json1':
        fail('unsupported_schema', '/schema_version')
    if envelope['record_type'] != record_type:
        fail('identity_mismatch', '/record_type')
    if type(envelope['content_sha256']) is not str or _HASH.fullmatch(envelope['content_sha256']) is None:
        fail('invalid_scalar', '/content_sha256')
    value = flow_from_payload(record_type, envelope['payload'], limits)
    if flow_content_digest(record_type, value) != envelope['content_sha256']:
        fail('digest_mismatch', '/content_sha256')
    if encode_flow_record(record_type, value) != data:
        fail('noncanonical', '')
    return value

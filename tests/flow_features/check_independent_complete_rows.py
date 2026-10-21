"""Execute externally reviewed complete-row expectations without generating them.

Usage: python -B check_independent_complete_rows.py ARTIFACT SHA256 LEASE RECEIPT
Only an explicitly pinned artifact is admitted. Receipts go to stdout and the
specified new private path; tracked documents and expected fixtures are untouched.
"""
from hashlib import sha256
from pathlib import Path
import json
import platform
import subprocess
import sys
import time

from option_flow_contracts import (
    FlowValidationError, decode_flow_request, decode_flow_snapshot,
    encode_flow_request, encode_flow_results, encode_flow_snapshot,
    flow_canonical_bytes, flow_from_payload, flow_record_digest, flow_to_payload,
)
from option_flow_features import evaluate_flow, replay_flow, restore_flow
from option_flow_features.engine import merge_flow_history
from check_independent_full_tranche import suffix_records


def require(condition, detail):
    if not condition:
        raise AssertionError(detail)


def same(actual, expected, label):
    require(actual == expected, f'{label}: actual={actual!r}; expected={expected!r}')


def first_difference(actual, expected, pointer=''):
    """Report the first differing closed field without dumping full records."""
    if type(actual) is not type(expected):
        return pointer, actual, expected
    if type(actual) is dict:
        if set(actual) != set(expected):
            return pointer + '/keys', sorted(actual), sorted(expected)
        for key in sorted(actual):
            difference = first_difference(actual[key], expected[key], pointer + '/' + key)
            if difference is not None:
                return difference
    elif type(actual) is list:
        if len(actual) != len(expected):
            return pointer + '/length', len(actual), len(expected)
        for index, (left, right) in enumerate(zip(actual, expected)):
            difference = first_difference(left, right, f'{pointer}/{index}')
            if difference is not None:
                return difference
    elif actual != expected:
        return pointer, actual, expected
    return None


def typed_request(source):
    if 'request_wire' in source:
        request = decode_flow_request(source['request_wire'].encode('utf-8'))
        same(encode_flow_request(request).decode('utf-8'), source['request_wire'], 'request wire')
    else:
        request = flow_from_payload('flow_request', source['request'])
    if 'request_record_sha256' in source:
        same(flow_record_digest('flow_request', request), source['request_record_sha256'], 'request identity')
    return request


def typed_snapshot(source):
    if 'snapshot_wire' in source:
        snapshot = decode_flow_snapshot(source['snapshot_wire'].encode('utf-8'))
        same(encode_flow_snapshot(snapshot).decode('utf-8'), source['snapshot_wire'], 'snapshot wire')
    else:
        snapshot = flow_from_payload('flow_snapshot', source['snapshot'])
    if 'snapshot_record_sha256' in source:
        same(flow_record_digest('flow_snapshot', snapshot), source['snapshot_record_sha256'], 'snapshot identity')
    return snapshot


def execute(source):
    """Return actual invocations with their genuine immutable input identities."""
    request = typed_request(source)
    operation = source['operation']
    if operation == 'restore':
        checkpoint = flow_from_payload('flow_checkpoint', source['checkpoint'])
        # A suffix is locally typed; its retained-prefix references resolve only
        # during actual merge/restore, not standalone snapshot decoding.
        suffix = suffix_records(source['snapshot'])
        checkpoint_hash = flow_record_digest('flow_checkpoint', checkpoint)
        if 'input_checkpoint_sha256' in source:
            same(checkpoint_hash, source['input_checkpoint_sha256'], 'input checkpoint identity')
        rows, _ = restore_flow(checkpoint, suffix, request)
        merged = merge_flow_history(checkpoint, suffix, request)
        direct = evaluate_flow(merged, request, input_checkpoint_sha256=checkpoint_hash)
        same(encode_flow_results(rows), encode_flow_results(direct), 'same-invocation restore/direct complete bytes')
        return [(rows, merged, request, checkpoint_hash)]
    snapshot = typed_snapshot(source)
    if operation == 'replay':
        requests = tuple(flow_from_payload('flow_request', payload) for payload in source['requests'])
        cuts = replay_flow(snapshot, requests)
        same(len(cuts), len(requests), 'actual replay invocation count')
        return [(rows, snapshot, cut, None) for rows, cut in zip(cuts, requests)]
    same(operation, 'evaluate', 'supported fixture operation')
    return [(evaluate_flow(snapshot, request), snapshot, request, None)]


def compare_invocation(actual, expected, ordinal):
    rows, snapshot, request, checkpoint_hash = actual
    if 'cut_index' in expected:
        same(expected['cut_index'], ordinal, 'independent cut index')
    for field, value in (
        ('snapshot_record_sha256', flow_record_digest('flow_snapshot', snapshot)),
        ('request_record_sha256', flow_record_digest('flow_request', request)),
        ('input_checkpoint_sha256', checkpoint_hash),
    ):
        if field in expected:
            same(value, expected[field], 'independent ' + field)
    difference = first_difference(flow_to_payload(rows), expected['expected_results'])
    require(difference is None, ('complete typed payload mismatch', difference))
    literal_bytes = json.dumps(expected['expected_results'], ensure_ascii=False, sort_keys=True,
                               separators=(',', ':'), allow_nan=False).encode('utf-8')
    same(flow_canonical_bytes(rows), literal_bytes, 'complete canonical result bytes')
    same(flow_record_digest('flow_results', rows), expected['expected_results_record_sha256'],
         'complete result record identity')
    same(encode_flow_results(rows).decode('utf-8'), expected['expected_results_wire'],
         'complete canonical result envelope bytes')
    return len(rows)


def source_hashes(root):
    paths = []
    for relative in ('packages/flow-contracts', 'packages/flow-features',
                     'tests/flow_contracts', 'tests/flow_features'):
        paths.extend(path for path in (root / relative).rglob('*') if path.is_file())
    return {path.relative_to(root).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths)}


def check(artifact_path, expected_sha256, lease, receipt_path):
    output = Path(receipt_path)
    require(not output.exists(), 'Receipt path already exists; preserve previous attempts and choose a new path')
    require(output.parent.is_dir(), 'Receipt parent directory must already exist')
    raw = Path(artifact_path).read_bytes()
    same(sha256(raw).hexdigest(), expected_sha256, 'externally pinned independent artifact SHA256')
    artifact = json.loads(raw)
    same(artifact['schema'], 'r26-independent-full-results1', 'closed independent artifact schema')
    root = Path(__file__).resolve().parents[2]
    before = source_hashes(root)
    started = time.perf_counter()
    failures = []
    successful = []
    full_cases = artifact['full_result_cases']
    control_families = (
        ('baseline_status', artifact['independent_baseline_status_controls']),
        ('observed_side_clock', artifact['independent_observed_side_clock_controls']),
    )
    same(len(full_cases), 66, 'independently reviewed full-case census')
    same(len(artifact['input_error_cases']), 19, 'independently reviewed input-error census')
    same(sum(len(controls) for _, controls in control_families), 5,
         'independently reviewed additional control census')
    same(len({case['id'] for case in full_cases}), len(full_cases), 'unique complete case IDs')
    full_invocations = 0
    control_invocations = 0
    complete_rows = 0
    operations = {'evaluate': 0, 'replay': 0, 'restore': 0}

    def failed(identity, error, category):
        item = {'id': identity, 'category': category,
                'exception_class': type(error).__name__, 'detail': str(error)}
        if isinstance(error, FlowValidationError):
            item['code'], item['path'] = error.code, error.path
        failures.append(item)
        print(json.dumps({'failure': item}), flush=True)

    for case in full_cases:
        identity = case['id']
        try:
            source = case['source_input']
            same(source['operation'], case['operation'], 'case operation identity')
            actual = execute(source)
            same(len(actual), len(case['invocations']), 'complete invocation census')
            row_count = 0
            for ordinal, (invocation, expected) in enumerate(zip(actual, case['invocations'])):
                row_count += compare_invocation(invocation, expected, ordinal)
            operations[source['operation']] += 1
            full_invocations += len(actual)
            complete_rows += row_count
            successful.append({'id': identity, 'category': 'full_result_case',
                               'invocations': len(actual), 'rows': row_count})
        except Exception as error:
            failed(identity, error, 'full_result_case')

    for category, controls in control_families:
        for case in controls:
            source = case['source_input']
            identity = source['id']
            try:
                require('operation' not in source, 'Literal controls use implicit evaluate operation')
                actual = execute(dict(source, operation='evaluate'))
                same(len(actual), 1, 'control invocation census')
                row_count = compare_invocation(actual[0], case, 0)
                control_invocations += 1
                complete_rows += row_count
                successful.append({'id': identity, 'category': category,
                                   'invocations': 1, 'rows': row_count})
            except Exception as error:
                failed(identity, error, category)

    originals = {case['id']: case for case in artifact['source_materialization']['cases']}
    same(len(originals), len(artifact['source_materialization']['cases']), 'unique source case IDs')
    error_passed = 0
    for case in artifact['input_error_cases']:
        identity = case['id']
        try:
            expected = case['expected_error']
            require(set(expected) <= {'code', 'path', 'exception_class'},
                    ('unsupported independently expected exception field', sorted(expected)))
            try:
                execute(originals[identity])
            except FlowValidationError as error:
                same(error.code, expected['code'], 'independent exception code')
                if 'path' in expected:
                    same(error.path, expected['path'], 'independent exception pointer')
                if 'exception_class' in expected:
                    same(type(error).__name__, expected['exception_class'], 'independent exception class')
            else:
                raise AssertionError('Expected boundary exception was not raised')
            error_passed += 1
            successful.append({'id': identity, 'category': 'input_error'})
        except Exception as error:
            failed(identity, error, 'input_error')

    after = source_hashes(root)
    if before != after:
        failed('source_manifest', AssertionError('Producer/test source changed during actual execution'), 'source_identity')
    receipt = {
        'lease': lease,
        'artifact_sha256': expected_sha256,
        'artifact_schema': artifact['schema'],
        'command': ['python', '-B', 'tests/flow_features/check_independent_complete_rows.py',
                    str(artifact_path), expected_sha256, lease, str(receipt_path)],
        'python': platform.python_version(),
        'platform': platform.platform(),
        'tracked_base_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root,
                                               capture_output=True, text=True, check=True).stdout.strip(),
        'source_state': 'Exact actual producer/test source hashes below; tracked base alone is not implementation identity',
        'expected_full_cases': len(full_cases),
        'full_cases_passed': sum(item['category'] == 'full_result_case' for item in successful),
        'full_invocations_passed': full_invocations,
        'operations_passed': operations,
        'expected_baseline_controls': len(control_families[0][1]),
        'expected_side_controls': len(control_families[1][1]),
        'controls_passed': control_invocations,
        'expected_input_errors': len(artifact['input_error_cases']),
        'input_errors_passed': error_passed,
        'complete_rows_passed': complete_rows,
        'successful': successful,
        'failures': failures,
        'elapsed_seconds': time.perf_counter() - started,
        'source_before': before,
        'source_after': after,
        'source_unchanged': before == after,
        'passed': not failures,
        'limitations': 'Source-development complete-row fixture consumption only; no installed artifacts, other platform, worker/storage/browser, producer integration or release qualification',
    }
    output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt, indent=2), flush=True)
    return not failures


if __name__ == '__main__':
    if len(sys.argv) != 5:
        raise SystemExit('Required: external artifact path, externally approved SHA256, actual lease ID, new private receipt path')
    raise SystemExit(0 if check(*sys.argv[1:]) else 1)

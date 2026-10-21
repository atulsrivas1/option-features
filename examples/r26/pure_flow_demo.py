"""Evaluate the original synthetic F01 tape using installed pure flow packages.

Run with an independently qualified contracts/features installation and -I -B.
File reading and presentation belong to this example, outside calculation code.
"""
import argparse
from pathlib import Path
import sys

from option_flow_contracts import decode_flow_request, decode_flow_snapshot, encode_flow_results
from option_flow_features import evaluate_flow


def rational_text(value):
    """Display the exact stored rational without recomputing any feature."""
    return 'null' if value is None else f'{value.numerator}/{value.denominator}'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--canonical', action='store_true',
                        help='Write the complete canonical results envelope as exact UTF-8 bytes.')
    args = parser.parse_args()
    directory = Path(__file__).resolve().parent
    snapshot = decode_flow_snapshot((directory / 'synthetic-snapshot.json').read_bytes())
    request = decode_flow_request((directory / 'request.json').read_bytes())
    results = evaluate_flow(snapshot, request)
    if args.canonical:
        # No added newline or text encoding changes: preserve the strict wire.
        sys.stdout.buffer.write(encode_flow_results(results))
    else:
        print('Original synthetic F01 option flow; exact rational values')
        print(f'Window [{request.window_start_ns}, {request.window_end_ns}); knowledge cutoff {request.knowledge_cutoff_ns}')
        for row in results:
            print(f'{row.group_id}  {row.output_id}: {rational_text(row.value)} {row.unit}'
                  f'  [{row.status}/{row.reason}; available_at={row.available_at_ns}]')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

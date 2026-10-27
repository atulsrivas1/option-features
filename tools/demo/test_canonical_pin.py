"""Pin export_demo.py's re-implemented canonical JSON and digests to the contracts package.

    python -I -B tools/demo/test_canonical_pin.py

Standard library only. The contracts source defaults to packages/option-contracts/src of this
repository; override with the OPTION_CONTRACTS_SRC environment variable.
"""
import os
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, os.environ.get("OPTION_CONTRACTS_SRC", str(HERE.parents[1] / "packages" / "option-contracts" / "src")))
sys.path.insert(0, str(HERE))
sys.dont_write_bytecode = True
import export_demo as demo  # noqa: E402
from option_feature_contracts.variants1 import canonical as lib  # noqa: E402

SAMPLES = [
    {}, [], {"b": 1, "a": [1, 2, {"z": None, "y": True}]},
    {"text": "caf\u00e9 \u4e2d\u6587 \U0001F600 \u2028", "esc": "\"\\n\t"},
    {"big": 9223372036854775807, "small": -9223372036854775808, "s": "123456789012345678901234567890"},
    {"price": {"bits": "4000000000000000", "kind": "b64"}, "n": {"bits": "7ff8000000000001", "kind": "b64"}},
    {"artifacts": [{"distribution": "duckdb", "version": "1.5.6", "wheel_sha256": "a" * 64}], "platform_id": "p"},
]


class Pin(unittest.TestCase):
    def test_canonical_json(self):
        for s in SAMPLES:
            self.assertEqual(demo.canonical_json(s), lib.canonical_json(s))

    def test_digests(self):
        for s in SAMPLES:
            for rt in ("variant_Result", "variant_Binding", "variant_Publication"):
                self.assertEqual(demo.content_digest(rt, s), lib.content_digest(rt, s))
                self.assertEqual(demo.record_digest(rt, s), lib.record_digest(rt, s))
            self.assertEqual(demo.cohort_digest(s), lib.cohort_digest(s))

    def test_envelope(self):
        import json
        for s in SAMPLES:
            text = demo.envelope("variant_Result", s)
            doc = json.loads(text)
            self.assertEqual(doc["content_sha256"], lib.content_digest("variant_Result", s))
            self.assertEqual(text.encode("utf-8"), lib.canonical_json(doc))


if __name__ == "__main__":
    unittest.main()

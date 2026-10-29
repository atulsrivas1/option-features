"""0.2.0a1 bump consistency: sources, pins, embedded result strings and the compatibility manifest agree."""
from decimal import Decimal
import json
from pathlib import Path
import tomllib
import unittest

import option_feature_contracts
import option_features
from p1_adapter import _evaluate_spread

ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.2.0a1"
LIVING = ("packages/features/pyproject.toml", "packages/option-contracts/pyproject.toml",
          "packages/features/src/option_features/__init__.py",
          "packages/option-contracts/src/option_feature_contracts/__init__.py",
          "packages/features/src/option_features/evaluator.py")
DOCS = (("docs/CONTRACTS_API.md", "option-feature-contracts==" + VERSION), ("docs/FEATURES_API.md", "option-features==" + VERSION))


class VersionBump(unittest.TestCase):
    def test_pyproject_versions_and_exact_pin(self):
        features = tomllib.loads((ROOT / "packages/features/pyproject.toml").read_text(encoding="utf-8"))["project"]
        contracts = tomllib.loads((ROOT / "packages/option-contracts/pyproject.toml").read_text(encoding="utf-8"))["project"]
        self.assertEqual((features["version"], contracts["version"]), (VERSION, VERSION))
        self.assertIn("option-feature-contracts==" + VERSION, features["dependencies"])

    def test_module_versions(self):
        self.assertEqual((option_features.__version__, option_feature_contracts.__version__), (VERSION, VERSION))

    def test_results_embed_the_new_version(self):
        (result,) = _evaluate_spread({"bid": "1.0000", "ask": "1.0200", "t_rel_ns": 0}, 10 ** 10, ["liquidity.spread_bps"])
        self.assertEqual((result.contracts_package_version, result.calculation_package_version), (VERSION, VERSION))

    def test_old_version_string_absent_from_living_sources(self):
        for name in LIVING:
            with self.subTest(file=name):
                self.assertNotIn("0.1.0a1", (ROOT / name).read_text(encoding="utf-8"))

    def test_living_docs_name_the_new_version(self):
        for name, text in DOCS:
            with self.subTest(file=name):
                self.assertIn(text, (ROOT / name).read_text(encoding="utf-8"))

    def test_compatibility_manifest(self):
        manifest = json.loads((ROOT / "docs/p1/COMPATIBILITY.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["packages"]["option-feature-contracts"]["version"], VERSION)
        self.assertEqual(manifest["packages"]["option-features"]["version"], VERSION)
        self.assertIn("option-feature-contracts==" + VERSION, manifest["packages"]["option-features"]["requires"])
        self.assertIs(manifest["packages"]["option-features"]["qualified"], False)
        for history in ("docs/r25/COMPATIBILITY.json", "docs/r26/COMPATIBILITY.json"):
            self.assertTrue((ROOT / history).exists())


if __name__ == "__main__":
    unittest.main()

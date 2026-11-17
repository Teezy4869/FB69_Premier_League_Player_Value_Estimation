"""G5: the official rs5 release is complete, checksummed, in scope, and its dataset is the audited one."""
from __future__ import annotations

import json
import re
import unittest

import yaml

from src.phase3.tm_common import file_hash
from src.research_scope.integrate_rs5 import DATASET_VERSION, RELEASE
from src.research_scope.scope import ROOT, SCOPE_PATH, load_scope

REQUIRED = {f"{DATASET_VERSION}.parquet", "data_dictionary.csv", "integration_manifest.json", "release_manifest.json", "SCOPE_DECLARATION.md", "research_scope.yaml", "PROVENANCE.md",
            "VALIDATION_SUMMARY.json", "README.md", "docs/LEAKAGE_AUDIT.md", "docs/TEMPORAL_ALIGNMENT_REPORT.md", "docs/DATA_QUALITY_REPORT.md", "docs/ISSUE_TRACKER.md", "docs/PHASE4_CONDITIONS.md"}


class ReleaseRs5Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((RELEASE / "release_manifest.json").read_text(encoding="utf-8"))
        cls.files = {p.relative_to(RELEASE).as_posix() for p in RELEASE.rglob("*") if p.is_file()}

    def test_required_contents_present(self):
        self.assertEqual(REQUIRED - self.files, set())

    def test_manifest_inventory_and_hashes(self):
        self.assertEqual({f["path"] for f in self.manifest["files"]}, self.files - {"release_manifest.json"})
        for f in self.manifest["files"]:
            self.assertEqual(file_hash(RELEASE / f["path"]), f["sha256"], f["path"])

    def test_scope_declared_and_snapshot_matches_config(self):
        scope = load_scope()
        self.assertEqual(self.manifest["seasons"], list(scope.labels))
        self.assertEqual(self.manifest["excluded_seasons"], ["2019/2020"])
        self.assertEqual(yaml.safe_load((RELEASE / "research_scope.yaml").read_text(encoding="utf-8")), yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8")))

    def test_dataset_is_the_audited_and_reproduced_one(self):
        summary = json.loads((RELEASE / "VALIDATION_SUMMARY.json").read_text(encoding="utf-8"))
        audit = json.loads((ROOT / "reports/research_scope_rs5/step_04/evidence/audit_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(audit["dataset_sha256"], file_hash(RELEASE / f"{DATASET_VERSION}.parquet"))
        self.assertTrue(summary["reproduction"]["all_identical"])
        self.assertEqual(summary["integration_checks"]["failed"], [])

    def test_historical_releases_untouched_by_name(self):
        for rel in self.manifest["historical_releases_preserved"]:
            self.assertTrue((ROOT / rel).exists())
        self.assertNotIn("2019", RELEASE.name)

    def test_release_documents_do_not_present_2019_20_as_data(self):
        """Mentions of 2019/20 in the release text may only explain the exclusion or historical context."""
        for name in ("README.md", "SCOPE_DECLARATION.md", "PROVENANCE.md"):
            text = (RELEASE / name).read_text(encoding="utf-8")
            for line in text.splitlines():
                if re.search(r"2019/20", line):
                    self.assertRegex(line.lower(), r"exclud|supersed|historical", f"{name}: {line}")


if __name__ == "__main__":
    unittest.main()

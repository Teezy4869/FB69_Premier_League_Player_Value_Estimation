"""G1: the central research scope is complete, consistent, and enforced. Fixtures here are SYNTHETIC tables."""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import duckdb
import yaml

from src.research_scope.scope import ROOT, SCOPE_PATH, ScopeViolation, assert_seasons, check_table, load_scope

FIVE = ("2020/2021", "2021/2022", "2022/2023", "2023/2024", "2024/2025")


class ScopeConfigTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scope = load_scope()
        cls.raw = yaml.safe_load(SCOPE_PATH.read_text(encoding="utf-8"))

    def test_exactly_the_five_approved_seasons(self):
        self.assertEqual(self.scope.labels, FIVE)
        self.assertEqual(len(set(self.scope.season_ids)), 5)
        self.assertEqual(self.scope.tm_start_years, (2020, 2021, 2022, 2023, 2024))
        self.assertEqual(self.scope.tm_year_range(), (2020, 2024))

    def test_2019_20_is_explicitly_excluded_everywhere(self):
        self.assertEqual(self.scope.excluded_labels, ("2019/2020",))
        self.assertEqual(self.scope.excluded_ids, ("14022",))
        self.assertEqual(self.scope.excluded_tm_years, (2019,))
        uses = set(self.raw["excluded_seasons"][0]["excluded_from"])
        self.assertTrue({"EDA", "feature_selection", "feature_engineering", "preprocessing", "model_training", "validation", "testing", "model_evaluation", "sensitivity_analysis"} <= uses)

    def test_objective_and_cutoff_policy_reference_existing_decisions(self):
        self.assertEqual(self.scope.objective_id, "A")
        self.assertEqual(self.raw["research_objective"]["decision_id"], "D6")
        self.assertEqual(self.scope.selection_rule_version, "latest_valid_on_or_before_season_end_v1")
        self.assertFalse(self.raw["season_cutoff_policy"]["stale_label_days_is_exclusion_rule"])

    def test_cutoffs_are_read_from_the_approved_config_not_copied(self):
        cutoffs = {s["season"]: s for s in yaml.safe_load((ROOT / "configs/phase_03_seasons.yaml").read_text(encoding="utf-8"))["seasons"]}
        for s in self.scope.seasons:
            self.assertEqual(s.season_end_date.isoformat(), cutoffs[s.season]["season_end_date"])
            self.assertEqual(s.season_id, str(cutoffs[s.season]["season_id"]))
        self.assertNotIn("season_end_date", SCOPE_PATH.read_text(encoding="utf-8"))

    def test_bad_configs_are_rejected(self):
        bad = dict(self.raw)
        bad["excluded_seasons"] = [{"season": "2020/2021", "season_id": "15382", "tm_season_start_year": 2020}]
        path = Path(self._tmp()) / "scope.yaml"
        path.write_text(yaml.safe_dump(bad), encoding="utf-8")
        with self.assertRaises(ScopeViolation):
            load_scope(path)
        bad = dict(self.raw)
        bad["research_objective"] = {"id": "B"}
        path.write_text(yaml.safe_dump(bad), encoding="utf-8")
        with self.assertRaises(ScopeViolation):
            load_scope(path)

    def _tmp(self):
        import tempfile
        folder = tempfile.mkdtemp(prefix="fb69_scope_test_")
        self.addCleanup(__import__("shutil").rmtree, folder, True)
        return folder


class ScopeEnforcementTest(unittest.TestCase):
    """Synthetic tables only: these rows are not research data."""

    @classmethod
    def setUpClass(cls):
        cls.scope = load_scope()

    def test_assert_seasons_rejects_excluded_season_in_every_form(self):
        for values, kind in ((["2019/2020"], "label"), (["14022"], "season_id"), ([2019], "tm_year")):
            with self.assertRaises(ScopeViolation):
                assert_seasons(values, self.scope, kind)

    def test_assert_seasons_rejects_unknown_and_null(self):
        with self.assertRaises(ScopeViolation):
            assert_seasons(["2025/2026"], self.scope)
        with self.assertRaises(ScopeViolation):
            assert_seasons([None], self.scope)
        self.assertEqual(assert_seasons(FIVE, self.scope), set(FIVE))

    def test_check_table_accepts_clean_and_rejects_contaminated(self):
        con = duckdb.connect()
        rows = ", ".join(f"('{s.season}', '{s.season_id}', {i})" for i, s in enumerate(self.scope.seasons))
        con.execute(f"CREATE TABLE ok AS SELECT * FROM (VALUES {rows}) t(season_label, season_id, x)")
        self.assertEqual(set(check_table(con, "ok", self.scope)["season_label"]), set(FIVE))
        con.execute("CREATE TABLE bad AS SELECT * FROM ok UNION ALL SELECT '2019/2020', '14022', 9")
        with self.assertRaises(ScopeViolation):
            check_table(con, "bad", self.scope)
        con.execute("CREATE TABLE mixed AS SELECT season_label, CASE WHEN season_label='2020/2021' THEN '16390' ELSE season_id END season_id FROM ok")
        with self.assertRaises(ScopeViolation):
            check_table(con, "mixed", self.scope)
        con.execute("CREATE TABLE partial AS SELECT * FROM ok WHERE season_label<>'2024/2025'")
        with self.assertRaises(ScopeViolation):
            check_table(con, "partial", self.scope)
        self.assertEqual(len(check_table(con, "partial", self.scope, require_all=False)["season_label"]), 4)


class NoLocalSeasonListsTest(unittest.TestCase):
    """rs5 code must take seasons from the central config, never from its own literals."""

    def test_rs5_sources_have_no_season_literals(self):
        literal = re.compile(r"['\"](20\d\d/20\d\d|20\d\d_20\d\d)['\"]|\b(14022|15382|16390|17664|20720|23685)\b|BETWEEN 20\d\d AND 20\d\d")
        offenders = []
        for path in sorted((ROOT / "src/research_scope").glob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if literal.search(line):
                    offenders.append(f"{path.name}:{number}: {line.strip()[:120]}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()

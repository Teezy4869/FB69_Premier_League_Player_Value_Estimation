"""Tests for defects found in the Step 3 QA audit, plus validator and adjudication rules.

Validator and adjudication unit tests use SYNTHETIC values. Real-output tests read the retained v1 and current runs.

Run: .venv/Scripts/python.exe -I -m unittest discover -s tests/phase3 -t . -v
"""
from __future__ import annotations

import csv
import filecmp
import json
import unittest
from datetime import date

import pyarrow.parquet as pq

from src.phase3.entity_resolution import ADJUDICATION_PATH, REVIEW_DIR, apply_adjudications, apply_review_decisions, generate_candidates, validate_crosswalk
from src.phase3.evaluate_matching import lower_bound
from src.phase3.step3_qa_adjudicate import decide
from src.phase3.step3_qa_validate import adjudicate, career_family, club_key, clubs_same, performance_family, physical_family, sensitivity_error_bound, upper_population_errors
from src.phase3.tm_common import ROOT, file_hash

V1 = ROOT / "data/phase_03/entity_resolution/matching_v1__reviews_none"
CURRENT = ROOT / "data/phase_03/entity_resolution/matching_v2_1__reviews_none"
EVIDENCE = ROOT / "reports/phase_03/step_03_qa/evidence"


def family(result):
    return {"result": result}


class ClubNameDefectTests(unittest.TestCase):
    """The false non-match for Zain Silcott-Duberry came from these abbreviations."""

    def same(self, a, b):
        return clubs_same(club_key(a), club_key(b))

    def test_abbreviations_and_spellings_match(self):
        self.assertTrue(self.same("Sheff Wed", "Sheffield Wednesday"))
        self.assertTrue(self.same("QPR", "Queens Park Rangers"))
        self.assertTrue(self.same("West Brom", "West Bromwich Albion"))
        self.assertTrue(self.same("Olympiacos", "Olympiakos CFP"))

    def test_different_clubs_stay_different(self):
        self.assertFalse(self.same("Real Madrid", "Real Betis"))
        self.assertFalse(self.same("Sheffield United", "Sheffield Wednesday"))
        self.assertFalse(self.same("Manchester City", "Manchester United"))

    def test_status_words_are_not_clubs(self):
        for word in ("Unknown", "Without Club", "Retired"):
            self.assertIsNone(club_key(word))


class ValidatorRuleTests(unittest.TestCase):
    def test_confirmation_needs_two_families_and_no_disagreement(self):
        self.assertEqual(adjudicate(family("AGREE"), family("AGREE"), family("MISSING"))["label"], "CONFIRMED_MATCH")
        self.assertEqual(adjudicate(family("AGREE"), family("AGREE"), family("DISAGREE"))["label"], "INCONCLUSIVE")
        self.assertEqual(adjudicate(family("AGREE"), family("MISSING"), family("UNINFORMATIVE"))["label"], "INCONCLUSIVE")

    def test_non_match_needs_two_disagreeing_families_and_no_agreement(self):
        self.assertEqual(adjudicate(family("DISAGREE"), family("DISAGREE"), family("MISSING"))["label"], "CONFIRMED_NON_MATCH")
        self.assertEqual(adjudicate(family("DISAGREE"), family("DISAGREE"), family("AGREE"))["label"], "INCONCLUSIVE")

    def test_inconclusive_is_never_positive(self):
        self.assertEqual(adjudicate(family("MISSING"), family("MISSING"), family("MISSING"))["label"], "INCONCLUSIVE")

    def test_career_ignores_epl_clubs_and_needs_a_date(self):
        epl = {"liverpool"}
        self.assertEqual(career_family([("liverpool", 2020)], [("liverpool", 2020)], epl)["result"], "UNINFORMATIVE")
        self.assertEqual(career_family([("porto", 2020)], [("porto", 2020)], epl)["result"], "AGREE")
        self.assertEqual(career_family([("porto", 2010)], [("porto", 2020)], epl)["result"], "UNINFORMATIVE")
        self.assertEqual(career_family([("porto", 2020), ("ajax", 2021)], [("lyon", 2020), ("roma", 2021)], epl)["result"], "DISAGREE")
        self.assertEqual(career_family([("porto", 2020)], [], epl)["result"], "MISSING")

    def test_physical(self):
        self.assertEqual(physical_family(180, 181, "right", "right")["result"], "AGREE")
        self.assertEqual(physical_family(180, 186, "right", "right")["result"], "DISAGREE")
        self.assertEqual(physical_family(180, 180, "left", "right")["result"], "DISAGREE")
        self.assertEqual(physical_family(None, None, None, None)["result"], "MISSING")
        self.assertEqual(physical_family(180, 183, "right", "both")["result"], "UNINFORMATIVE")

    def test_performance_needs_enough_events(self):
        same = {"goals": 2, "assists": 1, "yellow_cards": 1, "red_cards": 0, "minutes": 1000}
        self.assertEqual(performance_family({"s": same}, {"s": same})["result"], "AGREE")
        quiet = {"goals": 0, "assists": 0, "yellow_cards": 0, "red_cards": 0, "minutes": 100}
        self.assertEqual(performance_family({"s": quiet}, {"s": quiet})["result"], "UNINFORMATIVE")
        self.assertEqual(performance_family({"s": same}, {})["result"], "MISSING")
        self.assertEqual(performance_family({"s": same}, {"s": {**same, "goals": 9}})["result"], "DISAGREE")


class StatisticsTests(unittest.TestCase):
    def test_300_clean_labels_lower_bound_is_exact(self):
        self.assertAlmostEqual(lower_bound(300, 300), 0.05 ** (1 / 300), places=6)

    def test_228_clean_labels_do_not_reach_99_percent(self):
        self.assertLess(lower_bound(228, 228), 0.99)

    def test_finite_population_bound_with_no_errors(self):
        self.assertEqual(upper_population_errors(1299, 0, 1299), 0)
        self.assertGreater(upper_population_errors(228, 0, 1299), 0)

    def test_sensitivity_bound_grows_as_detection_weakens(self):
        self.assertLess(sensitivity_error_bound(0, 0.8), sensitivity_error_bound(0, 0.2))
        self.assertEqual(sensitivity_error_bound(0, 0.9), 1)


class AdjudicationTests(unittest.TestCase):
    def row(self, **extra):
        base = {"fotmob_names": "Toti Gomes", "tm_player_id": "1", "label": "INCONCLUSIVE", "confidence": "NONE", "dob_relation": "EXACT", "suggestion": "LIKELY_MATCH", "shared_games": 10, "fm_games": 10, "game_jaccard": 1.0, "career_result": "AGREE", "physical_result": "MISSING", "performance_result": "MISSING"}
        return {**base, **extra}

    def test_rule_confirmation_maps(self):
        self.assertEqual(decide([self.row(label="CONFIRMED_MATCH", confidence="HIGH")])["outcome"], "CONFIRMED_MATCH")

    def test_inconclusive_without_external_evidence_is_not_confirmed(self):
        self.assertEqual(decide([self.row()])["outcome"], "INSUFFICIENT_EVIDENCE")

    def test_external_needs_game_history_and_an_independent_family(self):
        good = self.row(fotmob_names="Quina")
        self.assertEqual(decide([good])["outcome"], "CONFIRMED_MATCH")
        self.assertEqual(decide([self.row(fotmob_names="Quina", career_result="MISSING")])["outcome"], "REVIEW_REQUIRED")
        self.assertEqual(decide([self.row(fotmob_names="Quina", shared_games=1, fm_games=1)])["outcome"], "REVIEW_REQUIRED")
        self.assertEqual(decide([self.row(fotmob_names="Quina", shared_games=0, game_jaccard=0.0)])["outcome"], "REVIEW_REQUIRED")

    def test_competing_candidates_block_a_decision(self):
        result = decide([self.row(label="CONFIRMED_MATCH"), self.row(tm_player_id="2")])
        self.assertEqual(result["outcome"], "REVIEW_REQUIRED")

    def test_only_confirmed_outcomes_on_unresolved_identities_apply(self):
        decisions = {"a": {"status": "REVIEW_REQUIRED", "method": "x", "tm_id": None}, "b": {"status": "REVIEW_REQUIRED", "method": "x", "tm_id": None}, "c": {"status": "AUTO_EXACT", "method": "x", "tm_id": "9"}}
        rows = [{"fotmob_player_id": "a", "tm_player_id": "1", "outcome": "CONFIRMED_MATCH", "basis": "RULE"}, {"fotmob_player_id": "b", "tm_player_id": "2", "outcome": "REVIEW_REQUIRED", "basis": "NONE"}, {"fotmob_player_id": "c", "tm_player_id": "3", "outcome": "CONFIRMED_MATCH", "basis": "RULE"}]
        self.assertEqual(apply_adjudications(decisions, rows, {"a": {"1"}, "b": {"2"}, "c": {"3"}}), 1)
        self.assertEqual(decisions["a"]["status"], "AUTO_ADJUDICATED")
        self.assertEqual(decisions["b"]["status"], "REVIEW_REQUIRED")
        self.assertEqual(decisions["c"]["tm_id"], "9")

    def test_adjudication_must_be_an_existing_candidate(self):
        with self.assertRaises(RuntimeError):
            apply_adjudications({"a": {"status": "REVIEW_REQUIRED", "method": "x", "tm_id": None}}, [{"fotmob_player_id": "a", "tm_player_id": "9", "outcome": "CONFIRMED_MATCH", "basis": "RULE"}], {"a": {"1"}})

    def test_human_decision_overrides_automation(self):
        decisions = {"a": {"status": "AUTO_ADJUDICATED", "method": "x", "tm_id": "1"}}
        review = {"fotmob_player_id": "a", "candidate_tm_player_id": "1", "reviewer_decision": "REJECT_CANDIDATE", "reviewer_name": "A", "review_date": "2026-11-05", "reviewer_notes": ""}
        apply_review_decisions(decisions, [review])
        self.assertEqual((decisions["a"]["status"], decisions["a"]["tm_id"]), ("REVIEW_REQUIRED", None))


class ReviewDefectTests(unittest.TestCase):
    def decision(self, name, tid="9", fid="1"):
        return {"fotmob_player_id": fid, "candidate_tm_player_id": tid, "reviewer_decision": name, "reviewer_name": "A", "review_date": "2026-11-05", "reviewer_notes": ""}

    def test_confirm_and_reject_of_one_pair_stops_the_run(self):
        with self.assertRaises(RuntimeError):
            apply_review_decisions({"1": {"status": "REVIEW_REQUIRED", "method": "x", "tm_id": None}}, [self.decision("CONFIRM_MATCH"), self.decision("REJECT_CANDIDATE")])

    def test_unknown_identity_gives_a_clear_error(self):
        with self.assertRaisesRegex(RuntimeError, "unknown FotMob identity"):
            apply_review_decisions({}, [self.decision("MARK_UNMATCHED")])

    def test_automated_decision_cannot_be_recorded_as_human(self):
        row = {"fotmob_player_id": "1", "canonical_player_id": "c", "transfermarkt_player_id": "9", "match_status": "AUTO_ADJUDICATED", "evidence": "{}"}
        with self.assertRaises(RuntimeError):
            validate_crosswalk([row])
        with self.assertRaises(RuntimeError):
            validate_crosswalk([{**row, "adjudicator": "automated", "reviewer": "A"}])
        self.assertFalse(any(validate_crosswalk([{**row, "adjudicator": "automated"}]).values()))


class DobNearDefectTests(unittest.TestCase):
    def test_equal_day_and_month_is_not_flagged_as_near(self):
        dob = date(1987, 9, 9)
        identity = {"names": {"Test Player"}, "dob": dob, "club_seasons": set(), "games": set()}
        players = {"1": {"normalized": "test player", "keys": {"player test"}}}
        index = {"by_key": {"player test": {"1"}}, "by_dob": {dob: {"1"}}, "by_year": {1987: {"1"}}, "by_club_season": {}, "by_game": {}}
        config = {"blocking": {"dob_exact_min_name_similarity": 40, "dob_near_min_name_similarity": 75, "roster_min_name_similarity": 70, "birth_year_min_name_similarity": 88, "game_set_min_jaccard": 0.8, "game_set_min_shared_games": 3}}
        blocks = generate_candidates(identity, players, index, config, include_fuzzy=True)
        self.assertNotIn("DOB_NEAR", blocks["1"])
        self.assertIn("DOB_EXACT", blocks["1"])


class RealOutputConsistencyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = pq.read_table(CURRENT / "player_crosswalk.parquet").to_pylist()
        cls.manifest = json.loads((CURRENT / "run_manifest.json").read_text(encoding="utf-8"))

    def test_v1_outputs_are_retained_unchanged(self):
        manifest = json.loads((V1 / "run_manifest.json").read_text(encoding="utf-8"))
        for name, sha in manifest["output_sha256"].items():
            self.assertEqual(file_hash(V1 / name), sha, name)
        self.assertTrue((V1 / "code_snapshot/entity_resolution.py").exists())
        self.assertTrue((V1 / "review_snapshot/matching_review_queue.csv").exists())

    def test_automatic_mappings_are_unchanged_from_v1(self):
        old = {r["fotmob_player_id"]: r["transfermarkt_player_id"] for r in pq.read_table(V1 / "player_crosswalk.parquet").to_pylist() if r["match_status"] == "AUTO_EXACT"}
        new = {r["fotmob_player_id"]: r["transfermarkt_player_id"] for r in self.rows if r["match_status"] == "AUTO_EXACT"}
        self.assertEqual(old, new)
        self.assertEqual(len(new), 1299)

    def test_validation_sample_is_identical_to_v1(self):
        self.assertTrue(filecmp.cmp(REVIEW_DIR / "validation_sample_for_labeling.csv", V1 / "review_snapshot/validation_sample_for_labeling.csv", shallow=False))

    def test_no_human_review_is_claimed(self):
        self.assertTrue(all(r["reviewer"] is None and r["review_date"] is None for r in self.rows))
        self.assertFalse((REVIEW_DIR / "review_decisions_ledger.csv").exists())
        with (REVIEW_DIR / "validation_sample_for_labeling.csv").open(encoding="utf-8-sig", newline="") as handle:
            self.assertTrue(all(not r["human_label"] for r in csv.DictReader(handle)))

    def test_automated_rows_are_labeled_as_automated(self):
        adjudicated = [r for r in self.rows if r["match_status"] == "AUTO_ADJUDICATED"]
        self.assertGreater(len(adjudicated), 0)
        for row in adjudicated:
            self.assertEqual(row["review_status"], "AUTOMATED_ADJUDICATION_NOT_HUMAN")
            self.assertTrue(row["adjudicator"].startswith("automated:"))

    def test_thin_cases_remain_unresolved(self):
        names = {r["fotmob_names_raw"]: r for r in self.rows}
        for name in ("Jimi Tauriainen", "Daniel Chesters"):
            self.assertEqual(names[name]["match_status"], "REVIEW_REQUIRED")
            self.assertIsNone(names[name]["transfermarkt_player_id"])

    def test_decisions_file_covers_the_44_and_matches_crosswalk(self):
        with ADJUDICATION_PATH.open(encoding="utf-8-sig", newline="") as handle:
            decisions = list(csv.DictReader(handle))
        self.assertEqual(len(decisions), 44)
        self.assertTrue(all(d["human_reviewed"] == "False" for d in decisions))
        status = {r["fotmob_player_id"]: r for r in self.rows}
        for decision in decisions:
            row = status[decision["fotmob_player_id"]]
            if decision["outcome"] == "CONFIRMED_MATCH":
                self.assertEqual(row["transfermarkt_player_id"], decision["tm_player_id"])
            else:
                self.assertIsNone(row["transfermarkt_player_id"])

    def test_counts_are_consistent_across_artifacts(self):
        summary = self.manifest["summary"]
        with (CURRENT / "unresolved_identities.csv").open(encoding="utf-8-sig", newline="") as handle:
            unresolved = list(csv.DictReader(handle))
        with (REVIEW_DIR / "matching_review_queue.csv").open(encoding="utf-8-sig", newline="") as handle:
            queue = list(csv.DictReader(handle))
        self.assertEqual(summary["status_identities"].get("REVIEW_REQUIRED", 0), len(unresolved))
        self.assertEqual(sum(summary["status_identities"].values()), len(self.rows))
        self.assertEqual(sum(summary["status_player_season_rows"].values()), 3262)
        self.assertEqual(len({q["fotmob_player_id"] for q in queue}), 44)
        candidates = pq.read_table(CURRENT / "matching_candidates.parquet", columns=["fotmob_player_id"]).to_pylist()
        self.assertEqual(summary["candidate_pairs"], len(candidates))

    def test_manifest_hashes_cover_every_output(self):
        files = {p.relative_to(CURRENT).as_posix() for p in CURRENT.rglob("*") if p.is_file() and p.name not in ("run_manifest.json", "matching_evaluation.json")}
        self.assertEqual(set(self.manifest["output_sha256"]), files)
        for name, sha in self.manifest["output_sha256"].items():
            self.assertEqual(file_hash(CURRENT / name), sha, name)

    def test_score_is_not_presented_as_confidence(self):
        columns = set(pq.read_schema(CURRENT / "player_crosswalk.parquet").names)
        self.assertIn("ranking_score", columns)
        self.assertNotIn("confidence_score", columns)

    def test_saved_validation_sample_has_required_fields_and_no_rule_reuse(self):
        with (EVIDENCE / "auto_match_validation_sample_300.csv").open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 300)
        for row in rows:
            self.assertIn(row["label"], ("CONFIRMED_MATCH", "CONFIRMED_NON_MATCH", "INCONCLUSIVE"))
            self.assertEqual(row["independent_of_name_dob_rule"], "True")
            self.assertEqual(row["human_reviewed"], "False")
            self.assertIn("AUTOMATED", row["adjudication_method"])


if __name__ == "__main__":
    unittest.main()

"""Tests for hybrid entity resolution.

Unit tests use SYNTHETIC candidates and temporary files. Real-output tests read the run folder and
fail if it is missing. A full rerun confirms the crosswalk is deterministic.

Run: .venv/Scripts/python.exe -I -m unittest discover -s tests/phase3 -t . -v
"""
from __future__ import annotations

import csv
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import duckdb
import pyarrow.parquet as pq
import yaml

from src.phase3.entity_resolution import (ADJUDICATION_PATH, CONFIG_PATH, LEDGER_COLUMNS, MAPPED_STATUSES, QUEUE_COLUMNS, REVIEW_DIR, STATUSES, apply_review_decisions, classify_identity, club_status, dob_relation,
                                          import_reviews, nationality_relation, resolve_tm_conflicts, run, score_candidate, suggest, validate_crosswalk, write_csv)
from src.phase3.evaluate_matching import evaluate, lower_bound
from src.phase3.names import is_token_subset, name_keys, normalize_name, sorted_tokens
from src.phase3.tm_common import FOTMOB_RELEASE, ROOT

CONFIG = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
RUN_DIR = ROOT / "data/phase_03/entity_resolution" / f"{CONFIG['matching_version']}__reviews_none"


def candidate(tm_id="1", name_exact=False, dob="DIFFERENT", club="ABSENT", suggestion="UNLIKELY", similarity=50.0, jaccard=0.0):
    return {"tm_player_id": tm_id, "name_exact": name_exact, "dob_relation": dob, "club_status": club, "suggestion": suggestion, "name_similarity": similarity, "game_jaccard": jaccard}


def crosswalk_row(fid="1", tid="9", status="AUTO_EXACT", evidence="{}"):
    return {"fotmob_player_id": fid, "canonical_player_id": f"fb69p_{fid}", "transfermarkt_player_id": tid, "match_status": status, "evidence": evidence}


class NameTests(unittest.TestCase):
    def test_token_order_is_handled(self):
        self.assertEqual(sorted_tokens(normalize_name("Son Heung-min")), sorted_tokens(normalize_name("Heung-min Son")))

    def test_umlaut_spelling_variant(self):
        self.assertTrue(name_keys(["Thomas Müller"]) & name_keys(["Thomas Mueller"]))

    def test_all_forms_contribute_keys(self):
        self.assertEqual(len(name_keys(["Ben White", "White Ben", "BEN  WHITE"])), 1)

    def test_tokens_are_not_dropped(self):
        self.assertNotEqual(name_keys(["Mads Bech"]), name_keys(["Mads Bech Sorensen"]))

    def test_subset(self):
        self.assertTrue(is_token_subset("alisson", "alisson becker"))
        self.assertFalse(is_token_subset("alison becker", "alisson becker"))
        self.assertFalse(is_token_subset(None, "x"))


class EvidenceTests(unittest.TestCase):
    def test_dob_relations(self):
        d = date(2000, 3, 5)
        self.assertEqual(dob_relation(d, d), "EXACT")
        self.assertEqual(dob_relation(d, date(2000, 3, 6)), "OFF_BY_ONE_DAY")
        self.assertEqual(dob_relation(d, date(2000, 5, 3)), "DAY_MONTH_SWAP")
        self.assertEqual(dob_relation(d, date(2000, 9, 9)), "SAME_YEAR")
        self.assertEqual(dob_relation(d, date(1999, 3, 5)), "DIFFERENT")
        self.assertEqual(dob_relation(None, d), "MISSING")

    def test_nationality_aliases_apply_to_both_sides(self):
        aliases = CONFIG["nationality_aliases"]
        self.assertEqual(nationality_relation("USA", "United States", aliases), "AGREE")
        self.assertEqual(nationality_relation("Turkiye", "Türkiye", aliases), "AGREE")
        self.assertEqual(nationality_relation("Turkiye", "Turkey", aliases), "AGREE")
        self.assertEqual(nationality_relation("Jamaica", "England", aliases), "DISAGREE")
        self.assertEqual(nationality_relation("France", None, aliases), "MISSING")

    def test_club_status(self):
        fm = {("2020/2021", "9")}
        self.assertEqual(club_status(fm, fm, 3), "CONFIRMED_GAMES")
        self.assertEqual(club_status(fm, fm, 0), "CONFIRMED_CLUB_SEASON")
        self.assertEqual(club_status(fm, {("2020/2021", "8")}, 0), "CONTRADICTED")

    def test_tm_gap_is_not_evidence_against_a_match(self):
        self.assertEqual(club_status({("2020/2021", "9")}, set(), 0), "ABSENT")
        self.assertEqual(club_status({("2020/2021", "9")}, {("2023/2024", "8")}, 0), "ABSENT")

    def test_missing_evidence_earns_no_points(self):
        signals = {"name_similarity": 100.0, "name_subset": False, "dob_relation": "MISSING", "tm_games": 0, "game_jaccard": 0.0, "nationality_relation": "MISSING", "position_relation": "MISSING"}
        score, available = score_candidate(signals, CONFIG["scoring"])
        weights = CONFIG["scoring"]
        self.assertEqual(score, weights["name_similarity"])
        self.assertEqual(available, weights["name_similarity"] + weights["name_subset"])

    def test_claimed_candidate_is_never_suggested_as_a_match(self):
        signals = {"dob_relation": "EXACT", "name_similarity": 100.0, "name_subset": True, "game_jaccard": 1.0, "club_status": "CONFIRMED_GAMES"}
        self.assertEqual(suggest(signals, CONFIG, True), "ALREADY_MAPPED_TO_ANOTHER_IDENTITY")

    def test_same_birth_date_alone_is_unlikely(self):
        signals = {"dob_relation": "EXACT", "name_similarity": 45.0, "name_subset": False, "game_jaccard": 0.0, "club_status": "ABSENT"}
        self.assertEqual(suggest(signals, CONFIG, False), "UNLIKELY")


class ClassificationTests(unittest.TestCase):
    def test_unique_exact_name_and_dob_maps(self):
        result = classify_identity([candidate(name_exact=True, dob="EXACT", club="CONFIRMED_GAMES")])
        self.assertEqual((result["status"], result["tm_id"]), ("AUTO_EXACT", "1"))

    def test_name_alone_never_maps(self):
        for dob in ("DIFFERENT", "SAME_YEAR", "OFF_BY_ONE_DAY", "MISSING"):
            result = classify_identity([candidate(name_exact=True, dob=dob, club="CONFIRMED_GAMES", similarity=100.0, jaccard=1.0)])
            self.assertIsNone(result["tm_id"], dob)
            self.assertEqual(result["status"], "REVIEW_REQUIRED")

    def test_high_fuzzy_score_never_maps(self):
        result = classify_identity([candidate(dob="EXACT", club="CONFIRMED_GAMES", suggestion="LIKELY_MATCH", similarity=99.0, jaccard=1.0)])
        self.assertIsNone(result["tm_id"])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")

    def test_non_unique_exact_is_ambiguous_without_mapping(self):
        result = classify_identity([candidate("1", True, "EXACT"), candidate("2", True, "EXACT")])
        self.assertEqual((result["status"], result["tm_id"]), ("AMBIGUOUS", None))

    def test_multiple_likely_candidates_are_ambiguous(self):
        result = classify_identity([candidate("1", suggestion="LIKELY_MATCH"), candidate("2", suggestion="LIKELY_MATCH")])
        self.assertEqual((result["status"], result["tm_id"]), ("AMBIGUOUS", None))

    def test_one_to_many_candidates_are_retained_for_review(self):
        result = classify_identity([candidate("1", suggestion="LIKELY_MATCH"), candidate("2"), candidate("3")])
        self.assertEqual(result["status"], "REVIEW_REQUIRED")

    def test_club_contradiction_goes_to_review(self):
        result = classify_identity([candidate(name_exact=True, dob="EXACT", club="CONTRADICTED")])
        self.assertEqual((result["status"], result["tm_id"]), ("REVIEW_REQUIRED", None))

    def test_no_candidates_is_unmatched(self):
        self.assertEqual(classify_identity([])["status"], "UNMATCHED")

    def test_shared_tm_id_becomes_ambiguous(self):
        decisions = {"a": {"status": "AUTO_EXACT", "method": "x", "tm_id": "9"}, "b": {"status": "AUTO_EXACT", "method": "x", "tm_id": "9"}, "c": {"status": "AUTO_EXACT", "method": "x", "tm_id": "8"}}
        self.assertEqual(resolve_tm_conflicts(decisions), ["9"])
        self.assertEqual((decisions["a"]["status"], decisions["a"]["tm_id"]), ("AMBIGUOUS", None))
        self.assertEqual(decisions["c"]["status"], "AUTO_EXACT")


class CrosswalkValidationTests(unittest.TestCase):
    def test_valid_crosswalk_passes(self):
        self.assertFalse(any(validate_crosswalk([crosswalk_row(), crosswalk_row("2", None, "REVIEW_REQUIRED", None)]).values()))

    def test_broken_rules_are_rejected(self):
        broken = {
            "duplicate fotmob": [crosswalk_row(), crosswalk_row("1", "8")],
            "duplicate tm": [crosswalk_row(), crosswalk_row("2", "9")],
            "bad status": [crosswalk_row(status="GUESS")],
            "ambiguous mapped": [crosswalk_row(status="AMBIGUOUS")],
            "unmatched mapped": [crosswalk_row(status="UNMATCHED")],
            "review mapped": [crosswalk_row(status="REVIEW_REQUIRED")],
            "mapped without id": [crosswalk_row(tid=None)],
            "no evidence": [crosswalk_row(evidence=None)],
        }
        for name, rows in broken.items():
            with self.assertRaises(RuntimeError, msg=name):
                validate_crosswalk(rows)


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.queue, self.ledger = Path(self.tmp.name) / "queue.csv", Path(self.tmp.name) / "ledger.csv"

    def queue_row(self, decision="", name="", when="", fid="1", tid="9"):
        return {"queue_id": f"{fid}:{tid}", "fotmob_player_id": fid, "candidate_tm_player_id": tid, "reviewer_decision": decision, "reviewer_name": name, "review_date": when, "reviewer_notes": ""}

    def test_blank_rows_create_no_decisions(self):
        write_csv(self.queue, QUEUE_COLUMNS, [self.queue_row()])
        self.assertEqual(import_reviews(self.queue, self.ledger, "now"), [])
        self.assertFalse(self.ledger.exists())

    def test_decision_needs_reviewer_and_date(self):
        write_csv(self.queue, QUEUE_COLUMNS, [self.queue_row("CONFIRM_MATCH")])
        with self.assertRaises(RuntimeError):
            import_reviews(self.queue, self.ledger, "now")

    def test_invalid_decision_is_rejected(self):
        write_csv(self.queue, QUEUE_COLUMNS, [self.queue_row("MAYBE", "A", "2026-11-05")])
        with self.assertRaises(RuntimeError):
            import_reviews(self.queue, self.ledger, "now")

    def test_ledger_survives_queue_regeneration(self):
        write_csv(self.queue, QUEUE_COLUMNS, [self.queue_row("CONFIRM_MATCH", "A", "2026-11-05")])
        first = import_reviews(self.queue, self.ledger, "t1")
        write_csv(self.queue, QUEUE_COLUMNS, [self.queue_row()])
        second = import_reviews(self.queue, self.ledger, "t2")
        self.assertEqual(len(first), 1)
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0]["reviewer_decision"], "CONFIRM_MATCH")
        self.assertEqual(second[0]["imported_at_utc"], "t1")

    def test_reimport_does_not_duplicate(self):
        write_csv(self.queue, QUEUE_COLUMNS, [self.queue_row("REJECT_CANDIDATE", "A", "2026-11-05")])
        import_reviews(self.queue, self.ledger, "t1")
        self.assertEqual(len(import_reviews(self.queue, self.ledger, "t2")), 1)

    def decision(self, name, fid="1", tid="9"):
        return {"fotmob_player_id": fid, "candidate_tm_player_id": tid, "reviewer_decision": name, "reviewer_name": "A", "review_date": "2026-11-05", "reviewer_notes": "", "imported_at_utc": "t"}

    def test_all_review_decisions_apply(self):
        expected = {"CONFIRM_MATCH": ("MANUAL_CONFIRMED", "9"), "MARK_AMBIGUOUS": ("AMBIGUOUS", None), "MARK_UNMATCHED": ("UNMATCHED", None), "INVESTIGATE": ("REVIEW_REQUIRED", None)}
        for name, (status, tid) in expected.items():
            decisions = {"1": {"status": "REVIEW_REQUIRED", "method": "x", "tm_id": None}}
            apply_review_decisions(decisions, [self.decision(name)])
            self.assertEqual((decisions["1"]["status"], decisions["1"]["tm_id"]), (status, tid), name)

    def test_rejecting_an_automatic_match_removes_it(self):
        decisions = {"1": {"status": "AUTO_EXACT", "method": "x", "tm_id": "9"}}
        apply_review_decisions(decisions, [self.decision("REJECT_CANDIDATE")])
        self.assertEqual((decisions["1"]["status"], decisions["1"]["tm_id"]), ("REVIEW_REQUIRED", None))

    def test_contradictory_decisions_stop_the_run(self):
        with self.assertRaises(RuntimeError):
            apply_review_decisions({"1": {"status": "REVIEW_REQUIRED", "method": "x", "tm_id": None}}, [self.decision("CONFIRM_MATCH"), self.decision("CONFIRM_MATCH", tid="8")])
        with self.assertRaises(RuntimeError):
            apply_review_decisions({"1": {"status": "REVIEW_REQUIRED", "method": "x", "tm_id": None}}, [self.decision("CONFIRM_MATCH"), self.decision("MARK_UNMATCHED")])


class EvaluationTests(unittest.TestCase):
    def label(self, fid, tid, label, stratum="OTHER", name="A", when="2026-11-05"):
        return {"sample_id": f"{stratum}:{fid}:{tid}", "stratum": stratum, "fotmob_player_id": fid, "candidate_tm_player_id": tid, "human_label": label, "labeler_name": name, "label_date": when}

    def test_blank_labels_claim_nothing(self):
        result = evaluate([self.label("1", "9", "", name="", when="")], {"1": "9"})
        self.assertEqual(result["status"], "NOT_EVALUATED")
        self.assertNotIn("sample_precision", result)

    def test_metrics_with_synthetic_labels(self):
        labels = [self.label("1", "9", "MATCH", "AUTO_EXACT_RANDOM"), self.label("2", "8", "NON_MATCH", "AUTO_EXACT_RANDOM"), self.label("3", "7", "MATCH"), self.label("4", "6", "NON_MATCH"), self.label("5", "5", "UNSURE")]
        result = evaluate(labels, {"1": "9", "2": "8"})
        self.assertEqual((result["true_positive"], result["false_positive"], result["false_negative"], result["true_negative"], result["unsure_excluded"]), (1, 1, 1, 1, 1))
        self.assertEqual(result["auto_exact_random"]["precision"], 0.5)

    def test_label_rules(self):
        with self.assertRaises(ValueError):
            evaluate([self.label("1", "9", "PROBABLY")], {})
        with self.assertRaises(ValueError):
            evaluate([self.label("1", "9", "MATCH", name="")], {})
        with self.assertRaises(ValueError):
            evaluate([self.label("1", "9", "MATCH"), self.label("1", "9", "NON_MATCH", "B")], {})

    def test_three_hundred_clean_labels_support_about_99_percent(self):
        self.assertAlmostEqual(lower_bound(300, 300), 0.99, places=2)
        self.assertLess(lower_bound(100, 100), 0.98)
        self.assertEqual(lower_bound(0, 0), 0.0)


class RealOutputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = pq.read_table(RUN_DIR / "player_crosswalk.parquet").to_pylist()
        cls.candidates = pq.read_table(RUN_DIR / "matching_candidates.parquet", columns=["fotmob_player_id", "tm_player_id", "name_exact", "dob_relation", "suggestion"]).to_pylist()
        cls.manifest = json.loads((RUN_DIR / "run_manifest.json").read_text(encoding="utf-8"))

    def test_population_is_complete(self):
        con = duckdb.connect()
        path = (FOTMOB_RELEASE / "normalized/confirmed_appeared_player_seasons.parquet").as_posix()
        ids = {r[0] for r in con.execute(f"SELECT DISTINCT player_id FROM read_parquet('{path}')").fetchall()}
        self.assertEqual({r["fotmob_player_id"] for r in self.rows}, ids)
        self.assertEqual(sum(r["player_season_rows"] for r in self.rows), 3262)

    def test_integrity_rules_hold(self):
        self.assertFalse(any(validate_crosswalk(self.rows).values()))

    def test_statuses_are_valid_and_high_confidence_is_off(self):
        statuses = {r["match_status"] for r in self.rows}
        self.assertLessEqual(statuses, set(STATUSES))
        self.assertNotIn("AUTO_HIGH_CONFIDENCE", statuses)
        self.assertFalse(CONFIG["auto_high_confidence"]["enabled"])

    def test_canonical_ids_are_stable_and_nameless(self):
        for row in self.rows:
            self.assertEqual(row["canonical_player_id"], f"fb69p_{row['fotmob_player_id']}")

    def test_every_automatic_match_is_exact_name_and_dob_against_source_data(self):
        lookup = {(c["fotmob_player_id"], c["tm_player_id"]): c for c in self.candidates}
        con = duckdb.connect()
        fm = dict(con.execute(f"SELECT player_id, birth_date FROM read_parquet('{(FOTMOB_RELEASE / 'normalized/players.parquet').as_posix()}')").fetchall())
        tm = dict(con.execute(f"SELECT tm_player_id, date_of_birth::VARCHAR FROM read_parquet('{(ROOT / 'data/transfermarkt/curated/tm_r2_20260905/tm_players.parquet').as_posix()}')").fetchall())
        checked = 0
        for row in self.rows:
            if row["match_status"] == "AUTO_EXACT":
                pair = lookup[(row["fotmob_player_id"], row["transfermarkt_player_id"])]
                self.assertTrue(pair["name_exact"])
                self.assertEqual(fm[row["fotmob_player_id"]], tm[row["transfermarkt_player_id"]])
                checked += 1
        self.assertGreater(checked, 0)

    def test_every_mapping_has_parseable_evidence(self):
        for row in self.rows:
            if row["transfermarkt_player_id"]:
                self.assertIn("dob_relation", json.loads(row["evidence"]))

    def test_unresolved_identities_are_retained_with_candidates(self):
        unresolved = [r for r in self.rows if r["match_status"] not in MAPPED_STATUSES]
        with (RUN_DIR / "unresolved_identities.csv").open(encoding="utf-8-sig", newline="") as handle:
            listed = {r["fotmob_player_id"] for r in csv.DictReader(handle)}
        self.assertEqual(listed, {r["fotmob_player_id"] for r in unresolved})
        for row in unresolved:
            self.assertIsNone(row["transfermarkt_player_id"])

    def test_automation_filled_no_reviewer_fields(self):
        for row in self.rows:
            self.assertIsNone(row["reviewer"])
            self.assertIsNone(row["review_date"])
        with (REVIEW_DIR / "matching_review_queue.csv").open(encoding="utf-8-sig", newline="") as handle:
            queue = list(csv.DictReader(handle))
        self.assertGreater(len(queue), 0)
        for row in queue:
            self.assertEqual([row[f] for f in ("reviewer_decision", "reviewer_name", "review_date", "reviewer_notes")], [""] * 4)

    def test_validation_labels_are_blank(self):
        with (REVIEW_DIR / "validation_sample_for_labeling.csv").open(encoding="utf-8-sig", newline="") as handle:
            sample = list(csv.DictReader(handle))
        self.assertGreater(len(sample), 300)
        self.assertTrue(all(not r["human_label"] for r in sample))

    def test_team_crosswalk_is_one_to_one(self):
        with (RUN_DIR / "team_crosswalk.csv").open(encoding="utf-8-sig", newline="") as handle:
            teams = list(csv.DictReader(handle))
        self.assertEqual(len(teams), 27)
        self.assertEqual(len({t["tm_club_id"] for t in teams}), 27)
        self.assertEqual(self.manifest["summary"]["fotmob_matches_aligned"], 2280)

    def test_rerun_is_deterministic(self):
        with tempfile.TemporaryDirectory() as folder:
            again = run(CONFIG, Path(folder) / "out", Path(folder) / "review", ADJUDICATION_PATH)
            run_dir = Path(again["run_dir"])
            con = duckdb.connect()
            for name in ("player_crosswalk.parquet", "matching_candidates.parquet"):
                new = con.execute(f"SELECT * FROM read_parquet('{(run_dir / name).as_posix()}')").fetchall()
                old = con.execute(f"SELECT * FROM read_parquet('{(RUN_DIR / name).as_posix()}')").fetchall()
                self.assertEqual(new, old, name)
            with (Path(folder) / "review/matching_review_queue.csv").open(encoding="utf-8-sig") as a, (REVIEW_DIR / "matching_review_queue.csv").open(encoding="utf-8-sig") as b:
                self.assertEqual(a.read(), b.read())


if __name__ == "__main__":
    unittest.main()

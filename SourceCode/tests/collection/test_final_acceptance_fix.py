import copy
import json
import tempfile
import unittest
from pathlib import Path

import pyarrow.parquet as pq

from src.collection.final_acceptance_fix import evaluate_match, population_status, raw_metadata, require_unique
from src.collection.remediation_substitutions import classify_participation_verified


def fixture():
    return {"match_id": "1", "competition_id": "47", "home_team_id": "10", "away_team_id": "20",
            "match_date_utc": "2024-01-01T12:00:00Z", "season_id": "s", "season_label": "2023/2024"}


def payload():
    def m(i, events=None):
        return {"id": i, "performance": {"substitutionEvents": events or []}}
    return {"general": {"matchId": "1", "leagueId": 47, "homeTeam": {"id": 10},
                        "awayTeam": {"id": 20}, "matchTimeUTCDate": "2024-01-01T12:00:00Z", "finished": True},
            "header": {"status": {"finished": True, "cancelled": False}},
            "content": {"lineup": {"lineupType": "standard",
                                   "homeTeam": {"starters": [m(1, [{"type": "subOut"}])],
                                                "subs": [m(2, [{"type": "subIn"}]), m(3)]},
                                   "awayTeam": {"starters": [m(4)], "subs": [m(5)]}},
                        "matchFacts": {"events": {"events": [{"type": "Goal"},
                             {"type": "Substitution", "swap": [{"id": 2}, {"id": 1}]}]}},
                        "playerStats": {}}}


class StrictEvidenceTests(unittest.TestCase):
    def test_starter_and_entering_substitute(self):
        e = evaluate_match(payload(), fixture())
        self.assertEqual(classify_participation_verified("1", "STARTER", e["starter_ids"], e["lineup_in"], e["fact_in"], e["completeness"])[0], "STARTED")
        self.assertEqual(classify_participation_verified("2", "SUBSTITUTE", e["starter_ids"], e["lineup_in"], e["fact_in"], e["completeness"])[0], "SUBSTITUTED_ON")

    def test_self_consistent_feed_does_not_prove_negative(self):
        e = evaluate_match(payload(), fixture())
        self.assertTrue(e["lineup_fact_in_agree"])
        self.assertEqual(e["completeness"], "PARTIAL")
        self.assertEqual(classify_participation_verified("3", "SUBSTITUTE", e["starter_ids"], e["lineup_in"], e["fact_in"], e["completeness"])[0], "UNKNOWN")

    def test_nonempty_but_incomplete_events(self):
        d = payload()
        d["content"]["matchFacts"]["events"]["events"] = [{"type": "Goal"}]
        e = evaluate_match(d, fixture())
        self.assertFalse(e["lineup_fact_in_agree"])
        self.assertEqual(e["completeness"], "PARTIAL")

    def test_missing_matchfacts(self):
        d = payload()
        del d["content"]["matchFacts"]
        self.assertEqual(evaluate_match(d, fixture())["completeness"], "UNVERIFIABLE")

    def test_no_substitution_events_is_not_negative(self):
        d = payload()
        for side in ("homeTeam", "awayTeam"):
            for role in ("starters", "subs"):
                for member in d["content"]["lineup"][side][role]:
                    member["performance"]["substitutionEvents"] = []
        d["content"]["matchFacts"]["events"]["events"] = [{"type": "Goal"}]
        e = evaluate_match(d, fixture())
        self.assertEqual(e["completeness"], "PARTIAL")
        self.assertEqual(classify_participation_verified("3", "SUBSTITUTE", e["starter_ids"], e["lineup_in"], e["fact_in"], e["completeness"])[0], "UNKNOWN")

    def test_explicit_unused_and_verified_complete_contract(self):
        args = ("3", "SUBSTITUTE", {"1", "4"}, {"2"}, {"2"})
        self.assertEqual(classify_participation_verified(*args, "PARTIAL", direct_unused=True)[0], "UNUSED_SUBSTITUTE")
        self.assertEqual(classify_participation_verified(*args, "COMPLETE_VERIFIED")[2], "COMPLETE_NEGATIVE_EVIDENCE")

    def test_conflicting_lineup_identity(self):
        d = payload()
        d["content"]["lineup"]["awayTeam"]["subs"].append({"id": 1})
        self.assertEqual(evaluate_match(d, fixture())["completeness"], "CONFLICTING")

    def test_malformed_swap(self):
        d = payload()
        d["content"]["matchFacts"]["events"]["events"][1]["swap"] = [{"id": 2}]
        self.assertEqual(evaluate_match(d, fixture())["completeness"], "CONFLICTING")

    def test_multiple_substitutions(self):
        d = payload()
        d["content"]["lineup"]["awayTeam"]["starters"][0]["performance"]["substitutionEvents"] = [{"type": "subOut"}]
        d["content"]["lineup"]["awayTeam"]["subs"][0]["performance"]["substitutionEvents"] = [{"type": "subIn"}]
        d["content"]["matchFacts"]["events"]["events"].append({"type": "Substitution", "swap": [{"id": 5}, {"id": 4}]})
        self.assertEqual(evaluate_match(d, fixture())["fact_substitution_count"], 2)

    def test_fact_only_positive_with_missing_lineup_sub_metadata(self):
        d = payload()
        del d["content"]["lineup"]["homeTeam"]["subs"][0]["performance"]
        e = evaluate_match(d, fixture())
        self.assertNotIn("2", e["lineup_in"])
        self.assertEqual(classify_participation_verified("2", "SUBSTITUTE", e["starter_ids"], e["lineup_in"], e["fact_in"], e["completeness"])[0], "SUBSTITUTED_ON")

    def test_wrong_team_and_invalid_player_id(self):
        d = payload()
        d["general"]["homeTeam"]["id"] = 99
        with self.assertRaises(ValueError):
            evaluate_match(d, fixture())
        e = evaluate_match(payload(), fixture())
        self.assertNotIn("999999", e["starter_ids"] | e["sub_ids"])

    def test_deterministic_evidence_evaluation(self):
        d = payload()
        self.assertEqual(evaluate_match(d, fixture()), evaluate_match(copy.deepcopy(d), fixture()))

    def test_wrong_scope_rejected(self):
        for path, value in (("matchId", "2"), ("leagueId", 99), ("finished", False)):
            d = payload()
            if path == "finished":
                d["header"]["status"][path] = value
            else:
                d["general"][path] = value
            with self.subTest(path=path), self.assertRaises(ValueError):
                evaluate_match(d, fixture())
        f = fixture()
        f["match_date_utc"] = "2022-01-01"
        with self.assertRaises(ValueError):
            evaluate_match(payload(), f)

    def test_duplicate_key_and_season_population(self):
        with self.assertRaises(ValueError):
            require_unique([{"match_id": "1", "player_id": "2"}] * 2, ("match_id", "player_id"), "test")
        self.assertEqual(population_status([{"participation_status": "UNKNOWN"}]), "UNVERIFIED")
        self.assertEqual(population_status([{"participation_status": "UNUSED_SUBSTITUTE"}], False), "UNVERIFIED")
        self.assertEqual(population_status([{"participation_status": "UNUSED_SUBSTITUTE"}], True), "CONFIRMED_NON_APPEARED")
        self.assertEqual(population_status([{"participation_status": "UNKNOWN"}, {"participation_status": "STARTED"}]), "CONFIRMED_APPEARED")

    def test_raw_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "response.json"
            path.write_text(json.dumps(payload()), encoding="utf-8")
            (root / "metadata.json").write_text(json.dumps({"content_sha256": "bad"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "RAW_CHECKSUM_MISMATCH"):
                raw_metadata(root, "response.json", fixture())

    def test_real_samples_all_six_seasons(self):
        root = Path(__file__).resolve().parents[2]
        v3 = root / "data/releases/fotmob_epl_2019_2025_v3/normalized"
        rows = pq.read_table(v3 / "player_match_appearances.parquet", columns=["season_label", "match_id", "raw_path"]).to_pylist()
        fixtures = {r["match_id"]: r for r in pq.read_table(v3 / "matches.parquet").to_pylist()}
        one = {}
        for r in rows:
            one.setdefault(r["season_label"], r)
        self.assertEqual(len(one), 6)
        for r in one.values():
            with self.subTest(season=r["season_label"]):
                d, sha = raw_metadata(root, r["raw_path"], fixtures[r["match_id"]])
                self.assertEqual(len(sha), 64)
                self.assertEqual(evaluate_match(d, fixtures[r["match_id"]])["completeness"], "PARTIAL")

    def test_real_replay_and_preserved_multiclub_relations(self):
        root = Path(__file__).resolve().parents[2]
        v3 = root / "data/releases/fotmob_epl_2019_2025_v3/normalized"
        staging = root / "data/staging/fotmob_epl_2019_2025_v3_1_provisional"
        rows = pq.read_table(v3 / "player_match_appearances.parquet", columns=["match_id", "raw_path"]).to_pylist()
        replay = next(r for r in rows if r["match_id"] == "4421797")
        match = next(r for r in pq.read_table(v3 / "matches.parquet").to_pylist() if r["match_id"] == "4421797")
        data, _ = raw_metadata(root, replay["raw_path"], match)
        self.assertEqual(evaluate_match(data, match)["completeness"], "PARTIAL")
        original = pq.read_table(v3 / "player_team_seasons.parquet", columns=["season_id", "player_id", "team_id"]).to_pylist()
        copied = pq.read_table(staging / "player_team_seasons.parquet", columns=["season_id", "player_id", "team_id"]).to_pylist()
        self.assertEqual(original, copied)


if __name__ == "__main__":
    unittest.main()

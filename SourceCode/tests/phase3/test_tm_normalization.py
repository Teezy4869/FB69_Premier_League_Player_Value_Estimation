"""Tests for the Transfermarkt acquisition and normalization pipeline.

FixtureTests uses SYNTHETIC data in a temporary folder that never touches research outputs.
SnapshotTests reads the real snapshot and outputs, and fails rather than skips if they are missing.

Run: .venv/Scripts/python.exe -I -m unittest discover -s tests/phase3 -t . -v
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import tempfile
import unittest
from pathlib import Path

import duckdb

from src.phase3.acquire_tm import PinMismatch, check_pin
from src.phase3.names import normalize_name
from src.phase3.normalize_tm import COLUMN_MAP, CONTRACT, build
from src.phase3.tm_common import ROOT, file_hash, load_config

SNAPSHOT = load_config()["snapshot_id"]
BASE = ROOT / "data/transfermarkt"
SOURCE = BASE / "source" / SNAPSHOT
CURATED = BASE / "curated" / SNAPSHOT
STAGING = BASE / "staging" / SNAPSHOT
METADATA = BASE / "metadata" / SNAPSHOT


def query(sql: str, *paths: Path):
    con = duckdb.connect(":memory:")
    return con.execute(sql.format(*[f"read_parquet('{p.as_posix()}')" for p in paths])).fetchall()


def write_fixture(folder: Path, overrides: dict[str, list[dict]]) -> None:
    """Write synthetic gzipped CSVs with the real headers. Tables not overridden have no rows."""
    for table, contract in CONTRACT.items():
        with gzip.open(folder / f"{table}.csv.gz", "wt", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(contract), quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(overrides.get(table, []))


SYNTHETIC = {
    "players": [
        {"player_id": "1", "name": "Synthetic Müller", "last_name": "Müller", "date_of_birth": "2000-01-02 00:00:00", "country_of_citizenship": "Testland", "position": "Attack", "player_code": "a", "url": "u1", "market_value_in_eur": "999", "highest_market_value_in_eur": "999", "current_club_id": "9"},
        {"player_id": "2", "name": "Synthetic Muller", "last_name": "Muller", "date_of_birth": "2000-01-02 00:00:00", "position": "Missing", "player_code": "b", "url": "u2"},
        {"player_id": "3", "name": "No Birthdate", "last_name": "Birthdate", "date_of_birth": "not-a-date", "position": "Defender", "player_code": "c", "url": "u3"},
    ],
    "player_valuations": [
        {"player_id": "1", "date": "2020-01-01", "market_value_in_eur": "1000", "current_club_name": "X", "current_club_id": "9"},
        {"player_id": "1", "date": "2020-02-01", "market_value_in_eur": "0", "current_club_name": "X", "current_club_id": "9"},
        {"player_id": "1", "date": "2020-03-01", "market_value_in_eur": "-5", "current_club_name": "X", "current_club_id": "9"},
        {"player_id": "1", "date": "2020-04-01", "market_value_in_eur": "12.5", "current_club_name": "X", "current_club_id": "9"},
        {"player_id": "1", "date": "2020-05-01", "market_value_in_eur": "", "current_club_name": "X", "current_club_id": "9"},
        {"player_id": "2", "date": "2021-02-30", "market_value_in_eur": "1000", "current_club_name": "X", "current_club_id": "9"},
        {"player_id": "2", "date": "2030-01-01", "market_value_in_eur": "1000", "current_club_name": "X", "current_club_id": "9"},
        {"player_id": "2", "date": "2021-06-01", "market_value_in_eur": "500", "current_club_name": "X", "current_club_id": "9"},
        {"player_id": "2", "date": "2021-06-01", "market_value_in_eur": "600", "current_club_name": "X", "current_club_id": "9"},
        {"player_id": "3", "date": "2021-07-01", "market_value_in_eur": "700", "current_club_name": "X", "current_club_id": "9"},
        {"player_id": "3", "date": "2021-07-01", "market_value_in_eur": "700", "current_club_name": "X", "current_club_id": "9"},
        {"player_id": "77", "date": "2021-08-01", "market_value_in_eur": "800", "current_club_name": "X", "current_club_id": "9"},
    ],
    "clubs": [{"club_id": "9", "club_code": "x", "name": "Club X", "domestic_competition_id": "GB1", "squad_size": "20", "foreigners_number": "1", "national_team_players": "1", "stadium_name": "s", "stadium_seats": "1", "net_transfer_record": "0", "last_season": "2024", "filename": "f", "url": "c"}],
    "competitions": [{"competition_id": "GB1", "competition_code": "pl", "name": "pl", "sub_type": "first_tier", "type": "domestic_league", "country_id": "1", "confederation": "e", "url": "k"}],
    "games": [
        {"game_id": "50", "competition_id": "GB1", "season": "2020", "round": "1", "date": "2020-09-12", "home_club_id": "9", "away_club_id": "8", "home_club_goals": "1", "away_club_goals": "0", "url": "g", "aggregate": "1:0"},
        {"game_id": "51", "competition_id": "CUP", "season": "2020", "round": "1", "date": "2020-09-13", "home_club_id": "9", "away_club_id": "8", "home_club_goals": "1", "away_club_goals": "0", "url": "h", "aggregate": "1:0"},
    ],
    "appearances": [
        {"appearance_id": "50_1", "game_id": "50", "player_id": "1", "player_club_id": "9", "player_current_club_id": "8", "date": "2020-09-12", "player_name": "n", "competition_id": "GB1", "yellow_cards": "0", "red_cards": "0", "goals": "0", "assists": "0", "minutes_played": "90"},
        {"appearance_id": "51_1", "game_id": "51", "player_id": "1", "player_club_id": "9", "player_current_club_id": "8", "date": "2020-09-13", "player_name": "n", "competition_id": "CUP", "yellow_cards": "0", "red_cards": "0", "goals": "0", "assists": "0", "minutes_played": "90"},
    ],
    "transfers": [{"player_id": "1", "transfer_date": "2099-01-01", "transfer_season": "98/99", "from_club_id": "8", "to_club_id": "9", "from_club_name": "A", "to_club_name": "B", "market_value_in_eur": "5.000", "player_name": "n"}],
}


class NameTests(unittest.TestCase):
    def test_cases(self):
        cases = {
            "Martin Ødegaard": "martin odegaard", "Emile Smith-Rowe": "emile smith rowe", "Dara O'Shea": "dara oshea",
            "Dara O’Shea": "dara oshea", "  N'Golo   KANTÉ ": "ngolo kante", "İlkay Gündoğan": "ilkay gundogan",
            "Łukasz Fabiański": "lukasz fabianski", "Son Heung-min": "son heung min", "Mateo Kovačić": "mateo kovacic",
            "Rúben Dias Jr.": "ruben dias jr",
        }
        for raw, expected in cases.items():
            self.assertEqual(normalize_name(raw), expected, raw)

    def test_empty_values_stay_null(self):
        self.assertIsNone(normalize_name(None))
        self.assertIsNone(normalize_name(" - "))

    def test_tokens_are_kept_in_order(self):
        self.assertEqual(normalize_name("De La Cruz"), "de la cruz")
        self.assertNotEqual(normalize_name("Ben White"), normalize_name("White Ben"))


class PinTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "f.csv.gz"
        self.path.write_bytes(b"synthetic")
        self.sha, self.md5 = file_hash(self.path), file_hash(self.path, "md5")

    def test_match(self):
        result = check_pin(self.path, {"name": "f", "bytes": 9, "sha256": self.sha, "etag": self.md5}, self.md5)
        self.assertEqual(result["pin_basis"], "APPROVED_SHA256")

    def test_mismatches_stop(self):
        bad = [{"bytes": 8, "sha256": self.sha}, {"bytes": 9, "sha256": "0" * 64}, {"bytes": 9, "sha256": None, "etag": "0" * 32}]
        for pin in bad:
            with self.assertRaises(PinMismatch):
                check_pin(self.path, {"name": "f", "etag": self.md5, **pin})

    def test_etag_change_stops(self):
        with self.assertRaises(PinMismatch):
            check_pin(self.path, {"name": "f", "bytes": 9, "sha256": self.sha, "etag": self.md5}, "different")


class FixtureTests(unittest.TestCase):
    """All records here are synthetic."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        root = Path(cls.tmp.name)
        cls.source = root / "source"
        cls.source.mkdir()
        write_fixture(cls.source, SYNTHETIC)
        cls.out = root / "a"
        cls.record = build(cls.source, cls.out)
        cls.valuations = cls.out / "curated/tm_valuation_history.parquet"
        cls.players = cls.out / "curated/tm_players.parquet"

    def status_of(self, player: str, raw_date: str) -> list:
        rows = query(f"SELECT quality_status FROM {{0}} WHERE tm_player_id='{player}' AND valuation_date_raw='{raw_date}'", self.valuations)
        return [r[0] for r in rows]

    def test_no_row_is_removed(self):
        self.assertEqual(self.record["curated_rows"]["tm_valuation_history"], len(SYNTHETIC["player_valuations"]))
        self.assertEqual(self.record["tables"]["player_valuations"]["staging_rows"], len(SYNTHETIC["player_valuations"]))

    def test_value_rules(self):
        self.assertEqual(self.status_of("1", "2020-01-01"), ["VALID"])
        self.assertEqual(self.status_of("1", "2020-02-01"), ["INVALID_VALUE_NONPOSITIVE"])
        self.assertEqual(self.status_of("1", "2020-03-01"), ["INVALID_VALUE_NONPOSITIVE"])
        self.assertEqual(self.status_of("1", "2020-04-01"), ["INVALID_VALUE_MISSING_OR_UNPARSEABLE"])
        self.assertEqual(self.status_of("1", "2020-05-01"), ["INVALID_VALUE_MISSING_OR_UNPARSEABLE"])

    def test_decimal_is_not_silently_rounded(self):
        row = query("SELECT market_value, market_value_raw FROM {0} WHERE valuation_date_raw='2020-04-01'", self.valuations)[0]
        self.assertIsNone(row[0])
        self.assertEqual(row[1], "12.5")

    def test_missing_value_is_not_zero(self):
        row = query("SELECT market_value FROM {0} WHERE valuation_date_raw='2020-05-01'", self.valuations)[0]
        self.assertIsNone(row[0])

    def test_date_rules(self):
        self.assertEqual(self.status_of("2", "2021-02-30"), ["INVALID_DATE"])
        self.assertEqual(self.status_of("2", "2030-01-01"), ["INVALID_DATE_AFTER_SNAPSHOT"])

    def test_conflict_and_duplicate_are_flagged_and_kept(self):
        self.assertEqual(self.status_of("2", "2021-06-01"), ["CONFLICT_SAME_DATE"] * 2)
        self.assertEqual(self.status_of("3", "2021-07-01"), ["DUPLICATE_EXACT"] * 2)

    def test_orphan_is_flagged(self):
        self.assertEqual(self.status_of("77", "2021-08-01"), ["ORPHAN_PLAYER"])

    def test_cast_failures_are_counted(self):
        failures = self.record["tables"]["player_valuations"]["cast_failures"]
        self.assertEqual(failures, {"date": 1, "market_value_in_eur": 1})
        self.assertEqual(self.record["tables"]["players"]["cast_failures"], {"date_of_birth": 1})

    def test_exceptions_file_lists_every_non_valid_row(self):
        with (self.out / "curated/tm_valuation_exceptions.csv").open(encoding="utf-8") as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), len(SYNTHETIC["player_valuations"]) - 1)

    def test_name_dob_collision_keeps_both_records(self):
        rows = query("SELECT tm_player_id FROM {0} WHERE is_name_dob_collision ORDER BY 1", self.players)
        self.assertEqual([r[0] for r in rows], ["1", "2"])

    def test_profile_market_values_never_reach_curated(self):
        columns = {r[0] for r in query("DESCRIBE SELECT * FROM {0}", self.players)}
        self.assertFalse(columns & {"market_value_in_eur", "highest_market_value_in_eur", "market_value"})

    def test_club_history_uses_only_gb1(self):
        rows = query("SELECT tm_player_id, tm_club_id, season_start_year, game_count FROM {0}", self.out / "curated/tm_player_club_seasons.parquet")
        self.assertEqual(rows, [("1", "9", 2020, 1)])

    def test_transfer_after_snapshot_is_flagged(self):
        self.assertEqual(query("SELECT is_after_snapshot FROM {0}", self.out / "curated/tm_transfers.parquet"), [(True,)])

    def test_header_change_stops_the_build(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)
            write_fixture(source, SYNTHETIC)
            with gzip.open(source / "clubs.csv.gz", "wt", encoding="utf-8") as handle:
                handle.write("club_id,surprise\n1,2\n")
            with self.assertRaises(RuntimeError):
                build(source, source / "out")

    def test_rebuild_is_identical(self):
        with tempfile.TemporaryDirectory() as folder:
            again = build(self.source, Path(folder) / "b")
        self.assertEqual(again["output_sha256"], self.record["output_sha256"])


class SnapshotTests(unittest.TestCase):
    """Checks against the real acquired snapshot and outputs."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((METADATA / "source_manifest.json").read_text(encoding="utf-8"))
        cls.schema = json.loads((METADATA / "schema_snapshot.json").read_text(encoding="utf-8"))
        cls.norm = json.loads((METADATA / "normalization_manifest.json").read_text(encoding="utf-8"))
        cls.valuations = CURATED / "tm_valuation_history.parquet"
        cls.players = CURATED / "tm_players.parquet"

    def test_raw_files_match_approved_pins_and_are_read_only(self):
        pins = {f["name"]: f for f in load_config()["files"]}
        self.assertEqual({p.name for p in SOURCE.iterdir()}, set(pins))
        for entry in self.manifest["files"]:
            path = SOURCE / entry["file"]
            self.assertEqual(file_hash(path), entry["sha256"])
            self.assertEqual(path.stat().st_size, pins[entry["file"]]["bytes"])
            if pins[entry["file"]]["sha256"]:
                self.assertEqual(entry["sha256"], pins[entry["file"]]["sha256"])
            self.assertFalse(os.access(path, os.W_OK))

    def test_manifest_records_provenance_and_rights(self):
        self.assertEqual(self.manifest["source"]["repository_commit"], "e44f186d6f06dd8452aaf54c7921ba66c961f637")
        self.assertEqual(self.manifest["rights"]["declared_license"], "CC0-1.0")
        self.assertEqual(self.manifest["rights"]["upstream_rights_status"], "NOT_INDEPENDENTLY_VERIFIED")

    def test_source_to_staging_row_counts(self):
        for table in CONTRACT:
            expected = self.schema["tables"][table]["records_csv_module"]
            actual = query("SELECT count(*) FROM {0}", STAGING / f"stg_{table}.parquet")[0][0]
            self.assertEqual(actual, expected, table)

    def test_staging_to_curated_row_counts(self):
        pairs = {"tm_players": "players", "tm_valuation_history": "player_valuations", "tm_clubs": "clubs", "tm_competitions": "competitions", "tm_transfers": "transfers"}
        for curated, staged in pairs.items():
            self.assertEqual(self.norm["curated_rows"][curated], self.norm["tables"][staged]["source_rows"], curated)

    def test_no_cast_failures(self):
        for table, stats in self.norm["tables"].items():
            self.assertEqual(stats["cast_failures"], {}, table)

    def test_output_hashes_match_manifest(self):
        for rel, sha in self.norm["output_sha256"].items():
            layer, name = rel.split("/")
            self.assertEqual(file_hash(BASE / layer / SNAPSHOT / name), sha, rel)

    def test_valuation_types(self):
        types = {r[0]: r[1] for r in query("DESCRIBE SELECT * FROM {0}", self.valuations)}
        self.assertEqual(types["tm_player_id"], "VARCHAR")
        self.assertEqual(types["valuation_date"], "DATE")
        self.assertEqual(types["market_value"], "BIGINT")
        self.assertEqual(types["currency"], "VARCHAR")
        self.assertEqual(types["reference_player_exists"], "BOOLEAN")

    def test_player_types(self):
        types = {r[0]: r[1] for r in query("DESCRIBE SELECT * FROM {0}", self.players)}
        self.assertEqual(types["tm_player_id"], "VARCHAR")
        self.assertEqual(types["date_of_birth"], "DATE")

    def test_club_season_types(self):
        types = {r[0]: r[1] for r in query("DESCRIBE SELECT * FROM {0}", CURATED / "tm_player_club_seasons.parquet")}
        self.assertEqual(types["minutes_played_sum"], "BIGINT")
        self.assertEqual(types["game_count"], "BIGINT")
        self.assertEqual(types["season_start_year"], "INTEGER")
        self.assertEqual(types["first_game_date"], "DATE")

    def test_no_curated_column_is_floating_point(self):
        for table in COLUMN_MAP:
            types = {r[1] for r in query("DESCRIBE SELECT * FROM {0}", CURATED / f"{table}.parquet")}
            self.assertFalse(types & {"DOUBLE", "FLOAT"}, table)

    def test_column_map_matches_outputs(self):
        for table, mapping in COLUMN_MAP.items():
            columns = {r[0] for r in query("DESCRIBE SELECT * FROM {0}", CURATED / f"{table}.parquet")}
            self.assertLessEqual(set(mapping), columns, table)

    def test_player_id_integrity(self):
        n, distinct, bad = query("SELECT count(*), count(DISTINCT tm_player_id), count(*) FILTER (WHERE NOT is_valid_player_id) FROM {0}", self.players)[0]
        self.assertEqual(n, distinct)
        self.assertEqual(bad, 0)

    def test_valuation_dates_and_raw_agree(self):
        self.assertEqual(query("SELECT count(*) FROM {0} WHERE valuation_date IS NULL OR valuation_date::VARCHAR<>valuation_date_raw", self.valuations)[0][0], 0)

    def test_valuation_values_equal_raw_text(self):
        self.assertEqual(query("SELECT count(*) FROM {0} WHERE market_value IS NULL OR market_value::VARCHAR<>market_value_raw", self.valuations)[0][0], 0)

    def test_valuation_is_still_observation_history(self):
        n, players = query("SELECT count(*), count(DISTINCT tm_player_id) FROM {0}", self.valuations)[0]
        self.assertGreater(n, players)
        self.assertEqual(query("SELECT count(*)-count(DISTINCT source_record_id) FROM {0}", self.valuations)[0][0], 0)

    def test_only_eur_is_present(self):
        self.assertEqual(query("SELECT DISTINCT currency FROM {0}", self.valuations), [("EUR",)])

    def test_every_non_valid_valuation_is_in_exceptions(self):
        expected = query("SELECT count(*) FROM {0} WHERE quality_status<>'VALID'", self.valuations)[0][0]
        with (CURATED / "tm_valuation_exceptions.csv").open(encoding="utf-8") as handle:
            self.assertEqual(len(list(csv.DictReader(handle))), expected)

    def test_valuation_lineage_points_to_source_row(self):
        path = SOURCE / "player_valuations.csv.gz"
        with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            first = [next(reader) for _ in range(500)]
        rows = query("SELECT _source_row_number, tm_player_id, valuation_date_raw, market_value_raw, _source_sha256 FROM {0} WHERE _source_row_number<=500 ORDER BY 1", self.valuations)
        self.assertEqual(len(rows), 500)
        for row, source in zip(rows, first):
            self.assertEqual((row[1], row[2], row[3]), (source["player_id"], source["date"], source["market_value_in_eur"]))
            self.assertEqual(row[4], file_hash(path) if row[0] == 1 else rows[0][4])

    def test_referential_integrity(self):
        self.assertEqual(query("SELECT count(*) FROM {0} ANTI JOIN {1} USING (tm_player_id)", self.valuations, self.players)[0][0], 0)
        self.assertEqual(query("SELECT count(*) FROM {0} ANTI JOIN {1} USING (tm_player_id)", CURATED / "tm_player_club_seasons.parquet", self.players)[0][0], 0)

    def test_club_season_key_is_unique_and_gb1(self):
        path = CURATED / "tm_player_club_seasons.parquet"
        self.assertEqual(query("SELECT count(*) FROM (SELECT 1 FROM {0} GROUP BY tm_player_id, tm_club_id, season_start_year HAVING count(*)>1)", path)[0][0], 0)
        self.assertEqual(query("SELECT DISTINCT competition_id FROM {0}", path), [("GB1",)])

    def test_real_rebuild_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as folder:
            again = build(SOURCE, Path(folder) / "rebuild")
        self.assertEqual(again["output_sha256"], self.norm["output_sha256"])


if __name__ == "__main__":
    unittest.main()

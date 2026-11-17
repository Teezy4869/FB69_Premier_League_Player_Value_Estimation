"""Central FB69 research scope: load configs/research_scope.yaml and enforce it.

All rs5 code asks this module which seasons are allowed. No rs5 module keeps its own season list.
The cutoff dates come from the approved cutoff config that the scope file references; they are not duplicated.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCOPE_PATH = ROOT / "configs/research_scope.yaml"


class ScopeViolation(RuntimeError):
    """Raised when data outside the official research scope reaches a research artifact."""


@dataclass(frozen=True)
class Season:
    season: str
    season_id: str
    tm_season_start_year: int
    first_match_date: date
    season_end_date: date
    cutoff_evidence: str


@dataclass(frozen=True)
class ResearchScope:
    scope_id: str
    seasons: tuple[Season, ...]
    excluded: tuple[dict, ...]
    objective_id: str
    selection_rule_version: str
    stale_label_days: int
    cutoff_config: Path
    raw: dict

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(s.season for s in self.seasons)

    @property
    def season_ids(self) -> tuple[str, ...]:
        return tuple(s.season_id for s in self.seasons)

    @property
    def tm_start_years(self) -> tuple[int, ...]:
        return tuple(s.tm_season_start_year for s in self.seasons)

    @property
    def excluded_labels(self) -> tuple[str, ...]:
        return tuple(e["season"] for e in self.excluded)

    @property
    def excluded_ids(self) -> tuple[str, ...]:
        return tuple(str(e["season_id"]) for e in self.excluded)

    @property
    def excluded_tm_years(self) -> tuple[int, ...]:
        return tuple(int(e["tm_season_start_year"]) for e in self.excluded)

    def by_label(self, label: str) -> Season:
        for s in self.seasons:
            if s.season == label:
                return s
        raise ScopeViolation(f"Season {label!r} is not an official research season")

    def sql_labels(self) -> str:
        return ", ".join(f"'{s}'" for s in self.labels)

    def sql_ids(self) -> str:
        return ", ".join(f"'{s}'" for s in self.season_ids)

    def tm_year_range(self) -> tuple[int, int]:
        years = sorted(self.tm_start_years)
        if years != list(range(years[0], years[-1] + 1)):
            raise ScopeViolation("Official seasons are not contiguous; a BETWEEN range would be wrong")
        return years[0], years[-1]


def load_scope(path: Path = SCOPE_PATH) -> ResearchScope:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    official = raw["official_seasons"]
    excluded = tuple(raw.get("excluded_seasons") or ())
    labels = [s["season"] for s in official]
    if len(labels) != len(set(labels)):
        raise ScopeViolation("Duplicate official season")
    overlap = set(labels) & {e["season"] for e in excluded}
    if overlap:
        raise ScopeViolation(f"Season both official and excluded: {sorted(overlap)}")
    if raw["research_objective"]["id"] != "A":
        raise ScopeViolation("The research objective must stay A (D6)")
    policy = raw["season_cutoff_policy"]
    cutoff_path = ROOT / policy["cutoff_config"]
    cutoffs = yaml.safe_load(cutoff_path.read_text(encoding="utf-8"))
    if cutoffs["selection_rule_version"] != policy["selection_rule_version"]:
        raise ScopeViolation("Scope and cutoff config disagree on the selection rule version")
    by_label = {s["season"]: s for s in cutoffs["seasons"]}
    seasons = []
    for s in official:
        c = by_label.get(s["season"])
        if c is None:
            raise ScopeViolation(f"No approved cutoff for {s['season']}")
        if c["verification_status"] != "VERIFIED":
            raise ScopeViolation(f"Cutoff for {s['season']} is not VERIFIED")
        if str(c["season_id"]) != str(s["season_id"]):
            raise ScopeViolation(f"season_id mismatch for {s['season']}")
        seasons.append(Season(s["season"], str(s["season_id"]), int(s["tm_season_start_year"]), date.fromisoformat(c["first_match_date"]),
                              date.fromisoformat(c["season_end_date"]), c["official_evidence"]))
    seasons.sort(key=lambda s: s.season)
    return ResearchScope(raw["scope_id"], tuple(seasons), excluded, raw["research_objective"]["id"], policy["selection_rule_version"],
                         int(cutoffs["stale_label_days"]), cutoff_path, raw)


def assert_seasons(values: Iterable, scope: ResearchScope | None = None, kind: str = "label", where: str = "") -> set:
    """Raise unless every value is an official season (label, FotMob season_id, or TM start year)."""
    scope = scope or load_scope()
    allowed = {"label": set(scope.labels), "season_id": set(scope.season_ids), "tm_year": set(scope.tm_start_years)}[kind]
    excluded = {"label": set(scope.excluded_labels), "season_id": set(scope.excluded_ids), "tm_year": set(scope.excluded_tm_years)}[kind]
    seen = {v if kind == "tm_year" else str(v) for v in values}
    if None in seen or "None" in seen:
        raise ScopeViolation(f"{where}: null season value")
    bad_excluded = seen & excluded
    if bad_excluded:
        raise ScopeViolation(f"{where}: excluded season present: {sorted(map(str, bad_excluded))}")
    unknown = seen - allowed
    if unknown:
        raise ScopeViolation(f"{where}: season outside the official scope: {sorted(map(str, unknown))}")
    return seen


def check_table(con, relation: str, scope: ResearchScope | None = None, label_col: str | None = "season_label", id_col: str | None = "season_id",
                require_all: bool = True, where: str = "") -> dict:
    """Validate one DuckDB relation. Returns per-season counts; raises ScopeViolation on any out-of-scope row."""
    scope = scope or load_scope()
    result = {}
    for col, kind in ((label_col, "label"), (id_col, "season_id")):
        if col is None:
            continue
        counts = dict(con.execute(f'SELECT "{col}", count(*) FROM {relation} GROUP BY 1').fetchall())
        assert_seasons(counts, scope, kind, f"{where or relation}.{col}")
        if require_all and set(counts) != set(scope.labels if kind == "label" else scope.season_ids):
            raise ScopeViolation(f"{where or relation}.{col}: missing official seasons {sorted(set(scope.labels if kind == 'label' else scope.season_ids) - set(counts))}")
        result[col] = {str(k): v for k, v in sorted(counts.items())}
    if label_col and id_col:
        pairs = con.execute(f'SELECT DISTINCT "{label_col}", "{id_col}" FROM {relation}').fetchall()
        expected = {(s.season, s.season_id) for s in scope.seasons}
        if not set(pairs) <= expected:
            raise ScopeViolation(f"{where or relation}: label/id pairs disagree: {sorted(set(pairs) - expected)}")
    return result


def check_parquet(path: Path, scope: ResearchScope | None = None, label_col: str | None = "season_label", id_col: str | None = "season_id", require_all: bool = True) -> dict:
    import duckdb

    con = duckdb.connect()
    relation = f"read_parquet('{Path(path).as_posix()}')"
    return check_table(con, relation, scope, label_col, id_col, require_all, where=Path(path).name)

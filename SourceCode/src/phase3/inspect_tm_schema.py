"""Inspect the acquired CSV files directly and write schema_snapshot.json (read-only on the snapshot)."""
from __future__ import annotations

import codecs
import csv
import gzip
import io
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import duckdb  # noqa: E402

from src.phase3.tm_common import ROOT, file_hash, load_config, write_json  # noqa: E402

NULL_TOKENS = ("null", "none", "nan", "n/a", "na", "-", "unknown", "missing", "?")
csv.field_size_limit(1 << 24)


def shape(value: str) -> str:
    return re.sub(r"[A-Za-z]+", "A", re.sub(r"\d", "9", value))[:32]


def raw_profile(path: Path) -> dict:
    """Strict UTF-8 decode and an independent record count using the csv module."""
    with gzip.open(path, "rb") as handle:
        first = handle.read(1 << 16)
    with gzip.open(path, "rb") as handle:
        decoder = io.TextIOWrapper(handle, encoding="utf-8", errors="strict", newline="")
        reader = csv.reader(decoder, delimiter=",", quotechar='"', doublequote=True, strict=True)
        header = next(reader)
        count = bad_width = 0
        for row in reader:
            count += 1
            bad_width += len(row) != len(header)
    return {
        "encoding": "utf-8 (strict decode of all bytes succeeded)", "bom": first.startswith(codecs.BOM_UTF8),
        "delimiter": ",", "quotechar": '"', "line_ending": "CRLF" if b"\r\n" in first else "LF",
        "header": header, "records_csv_module": count, "rows_with_wrong_width": bad_width,
    }


def inspect(path: Path) -> dict:
    con = duckdb.connect(":memory:")
    con.execute("SET threads=1")
    posix = path.as_posix()
    profile = raw_profile(path)
    con.execute(f"CREATE TABLE t AS SELECT * FROM read_csv('{posix}', all_varchar=true, header=true, delim=',', quote='\"', escape='\"')")
    sniffed = {r[0]: r[1] for r in con.execute(f"DESCRIBE SELECT * FROM read_csv('{posix}', header=true, sample_size=-1)").fetchall()}
    total = con.execute("SELECT count(*) FROM t").fetchone()[0]
    columns = []
    for name in profile["header"]:
        q = f'"{name}"'
        nulls, empty, padded, distinct, min_len, max_len = con.execute(
            f"SELECT count(*)-count({q}), count(*) FILTER (WHERE {q}=''), count(*) FILTER (WHERE {q}<>trim({q})), "
            f"count(DISTINCT {q}), min(length({q})), max(length({q})) FROM t").fetchone()
        tokens = dict(con.execute(f"SELECT lower(trim({q})), count(*) FROM t WHERE lower(trim({q})) IN {NULL_TOKENS} GROUP BY 1").fetchall())
        values = [r[0] for r in con.execute(f"SELECT {q} FROM t WHERE {q} IS NOT NULL").fetchall()]
        columns.append({
            "name": name, "sniffed_type": sniffed.get(name), "nulls": nulls, "empty_strings": empty,
            "whitespace_padded": padded, "distinct": distinct, "min_length": min_len, "max_length": max_len,
            "null_like_tokens": tokens, "top_value_shapes": Counter(shape(v) for v in values).most_common(4),
        })
    sample = con.execute("SELECT * FROM t LIMIT 3").fetchall()
    return {
        "file": path.name, "gz_bytes": path.stat().st_size, "gz_sha256": file_hash(path), **profile,
        "records_duckdb": total, "counts_agree": total == profile["records_csv_module"],
        "columns": columns, "sample_rows": [dict(zip(profile["header"], row)) for row in sample],
    }


def main() -> None:
    config = load_config()
    snapshot_id = config["snapshot_id"]
    tables = {}
    for pin in config["files"]:
        table = pin["name"].removesuffix(".csv.gz")
        tables[table] = inspect(ROOT / "data/transfermarkt/source" / snapshot_id / pin["name"])
        print(table, tables[table]["records_duckdb"], tables[table]["records_csv_module"], tables[table]["rows_with_wrong_width"])
    write_json(ROOT / "data/transfermarkt/metadata" / snapshot_id / "schema_snapshot.json", {
        "snapshot_id": snapshot_id, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "duckdb_version": duckdb.__version__, "format": "gzipped CSV; source files carry no declared types",
        "sniffed_type_note": "sniffed_type is DuckDB's inference over all rows, not a source declaration.",
        "tables": tables,
    })


if __name__ == "__main__":
    main()

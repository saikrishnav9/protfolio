from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import duckdb


def connect(db_path: Path | None = None) -> duckdb.DuckDBPyConnection:
    if db_path is None:
        return duckdb.connect(database=":memory:")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, default=str) + "\n")


def payload_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def write_parquet(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> int:
    """Write rows to parquet with a stable schema even when empty."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = connect()
    if not rows:
        selects = ", ".join(f"NULL AS {col}" for col in columns)
        con.execute(f"COPY (SELECT {selects} WHERE 1=0) TO '{path.as_posix()}' (FORMAT PARQUET)")
        return 0
    json_path = path.with_suffix(".staging.json")
    write_json(json_path, rows)
    con.execute(
        f"""
        COPY (
          SELECT {", ".join(columns)}
          FROM read_json_auto('{json_path.as_posix()}', format='array')
        ) TO '{path.as_posix()}' (FORMAT PARQUET)
        """
    )
    json_path.unlink(missing_ok=True)
    return len(rows)


def copy_parquet_or_empty(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        dest.write_bytes(src.read_bytes())

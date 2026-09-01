"""Execução paginada de queries no DuckDB."""

from __future__ import annotations

import duckdb


def count_from_sql(con: duckdb.DuckDBPyConnection, from_clause: str) -> int:
    row = con.execute(f"SELECT COUNT(*) FROM {from_clause}").fetchone()
    assert row is not None
    return int(row[0])

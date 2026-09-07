"""Contagem de linhas no DuckDB."""

from __future__ import annotations

import duckdb

from pq.db.sql_utils import strip_sql


def count_query(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    """COUNT(*) sobre um SELECT/WITH (sem carregar o resultado)."""
    query = strip_sql(sql)
    row = con.execute(f"SELECT COUNT(*) FROM ({query}) __q__").fetchone()
    assert row is not None
    return int(row[0])


def count_from_sql(con: duckdb.DuckDBPyConnection, from_clause: str) -> int:
    """COUNT(*) a partir de um FROM clause (`"tabela"` ou subquery)."""
    row = con.execute(f"SELECT COUNT(*) FROM {from_clause}").fetchone()
    assert row is not None
    return int(row[0])

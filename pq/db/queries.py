"""Execução paginada de queries no DuckDB."""

from __future__ import annotations

import duckdb
import pandas as pd

from pq.db.sql_utils import strip_sql


def fetch_sql_page(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    *,
    page: int,
    page_size: int,
) -> tuple[pd.DataFrame, int]:
    """Executa COUNT + LIMIT/OFFSET no DuckDB; retorna (dataframe, total)."""
    query = strip_sql(sql)
    total = con.execute(f"SELECT COUNT(*) FROM ({query}) __q__").fetchone()[0]
    offset = (page - 1) * page_size
    df = con.execute(
        f"SELECT * FROM ({query}) __q__ LIMIT {page_size} OFFSET {offset}"
    ).df()
    return df, total


def count_from_sql(con: duckdb.DuckDBPyConnection, from_clause: str) -> int:
    return con.execute(f"SELECT COUNT(*) FROM {from_clause}").fetchone()[0]

"""Conexão DuckDB e registro de views sobre arquivos."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st


@st.cache_resource
def get_connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


def duckdb_read_expr(path: Path) -> str:
    ext = path.suffix.lower()
    posix = path.as_posix().replace("'", "''")
    if ext == ".parquet":
        return f"read_parquet('{posix}')"
    if ext == ".csv":
        return f"read_csv_auto('{posix}')"
    raise ValueError(f"Formato não suportado para leitura: {ext}")


def register_view(con: duckdb.DuckDBPyConnection, name: str, path: Path) -> None:
    source = duckdb_read_expr(path)
    con.execute(f'CREATE OR REPLACE VIEW "{name}" AS SELECT * FROM {source}')


def list_views(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [row[0] for row in con.execute("SHOW TABLES").fetchall()]


def run_query(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(sql).df()

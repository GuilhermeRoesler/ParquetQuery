"""Schema e metadados de tabelas DuckDB (com cache Streamlit)."""

from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from pq.db.connection import get_connection


@st.cache_data(ttl=300)
def get_schema(table: str) -> pd.DataFrame:
    con = get_connection()
    return con.execute(f'DESCRIBE "{table}"').df()


@st.cache_data(ttl=300)
def count_rows(table: str) -> int:
    con = get_connection()
    return con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def describe_sql(con: duckdb.DuckDBPyConnection, sql: str) -> pd.DataFrame:
    return con.execute(f"DESCRIBE ({sql})").df()


def table_column_names(
    con: duckdb.DuckDBPyConnection,
    table: str,
    derived_sql: str | None,
) -> list[str]:
    if derived_sql:
        df = describe_sql(con, derived_sql)
    else:
        df = get_schema(table)
    return df["column_name"].tolist()

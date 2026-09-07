"""Schema e metadados de tabelas DuckDB (com cache Streamlit)."""

from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from pq.db.connection import get_connection
from pq.db.sql_utils import quote_ident


@st.cache_data(ttl=300)
def get_schema(table: str) -> pd.DataFrame:
    con = get_connection()
    return con.execute(f"DESCRIBE {quote_ident(table)}").df()


@st.cache_data(ttl=300)
def describe_sql_cached(sql: str) -> pd.DataFrame:
    """DESCRIBE de um SELECT na conexão compartilhada (sem passar con)."""
    con = get_connection()
    return con.execute(f"DESCRIBE ({sql})").df()


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
    return [str(name) for name in df["column_name"].tolist()]

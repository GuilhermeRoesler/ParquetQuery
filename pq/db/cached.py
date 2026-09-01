"""Queries de overview com cache Streamlit."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pq.db.connection import get_connection
from pq.overview.sql import build_classificatory_overview_sql, build_numeric_overview_sql


@st.cache_data(ttl=300)
def get_classificatory_overview(
    table: str,
    col: str,
    derived_sql: str | None,
) -> pd.DataFrame:
    con = get_connection()
    sql = build_classificatory_overview_sql(table, col, derived_sql)
    return con.execute(sql).df()


@st.cache_data(ttl=300)
def get_numeric_overview(
    table: str,
    col: str,
    agg: str,
    dtype: str,
    derived_sql: str | None,
):
    con = get_connection()
    sql = build_numeric_overview_sql(table, col, agg, dtype, derived_sql)
    return con.execute(sql).fetchone()[0]


def clear_overview_cache() -> None:
    get_classificatory_overview.clear()
    get_numeric_overview.clear()

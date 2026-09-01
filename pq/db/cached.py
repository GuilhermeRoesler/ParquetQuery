"""Queries de overview com cache Streamlit."""

from __future__ import annotations

import streamlit as st

from pq.db.connection import get_connection
from pq.overview.sql import (
    build_classificatory_overview_summary_sql,
    build_numeric_overview_sql,
)


@st.cache_data(ttl=300)
def get_classificatory_overview_summary(
    table: str,
    col: str,
    derived_sql: str | None,
) -> tuple[int, int]:
    """Retorna (valores_distintos, linhas_contabilizadas) sem carregar GROUP BY na RAM."""
    con = get_connection()
    sql = build_classificatory_overview_summary_sql(table, col, derived_sql)
    row = con.execute(sql).fetchone()
    return int(row[0]), int(row[1])


@st.cache_data(ttl=300)
def get_numeric_overview(
    table: str,
    col: str,
    agg: str,
    dtype: str,
    derived_sql: str | None,
) -> object:
    con = get_connection()
    sql = build_numeric_overview_sql(table, col, agg, dtype, derived_sql)
    return con.execute(sql).fetchone()[0]


def clear_overview_cache() -> None:
    get_classificatory_overview_summary.clear()
    get_numeric_overview.clear()

"""Componentes reutilizáveis de paginação."""

from __future__ import annotations

from typing import NamedTuple

import duckdb
import pandas as pd
import streamlit as st

from pq.db.sql_utils import strip_sql


class PageInfo(NamedTuple):
    page: int
    pages: int
    total: int
    page_size: int


def _pagination_page(key: str, pages: int) -> int:
    state_key = f"pg_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = 1
    page = int(st.session_state[state_key])
    page = max(1, min(page, pages))
    st.session_state[state_key] = page
    return page


def render_pagination_bar(key: str, info: PageInfo) -> None:
    if info.pages <= 1:
        if info.total > 0:
            with st.container(horizontal=True, horizontal_alignment="center"):
                st.caption(f"{info.total:,} linha(s)")
        return

    pk = f"pg_{key}"
    start = (info.page - 1) * info.page_size + 1
    end = min(info.page * info.page_size, info.total)

    with st.container(
        horizontal=True,
        horizontal_alignment="center",
        vertical_alignment="center",
        gap="small",
    ):
        if st.button("◀", key=f"{pk}_prev", disabled=info.page <= 1):
            st.session_state[pk] = info.page - 1
            st.rerun()
        st.markdown(
            f"<span style='font-size:0.875rem;white-space:nowrap'>{start:,}–{end:,} de {info.total:,} · "
            f"<strong>{info.page}/{info.pages}</strong></span>",
            unsafe_allow_html=True,
        )
        if st.button("▶", key=f"{pk}_next", disabled=info.page >= info.pages):
            st.session_state[pk] = info.page + 1
            st.rerun()


def show_paginated_dataframe(df: pd.DataFrame, info: PageInfo, key: str) -> None:
    st.dataframe(df, use_container_width=True, hide_index=True)
    render_pagination_bar(key, info)


def paginate(df: pd.DataFrame, key: str, page_size: int = 500) -> tuple[pd.DataFrame, PageInfo]:
    total = len(df)
    pages = max(1, (total + page_size - 1) // page_size)
    page = _pagination_page(key, pages)
    offset = (page - 1) * page_size
    info = PageInfo(page, pages, total, page_size)
    return df.iloc[offset : offset + page_size], info


def paginate_sql(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    key: str,
    page_size: int = 500,
) -> tuple[pd.DataFrame, PageInfo]:
    """Paginação diretamente no DuckDB — não carrega tudo na RAM."""
    query = strip_sql(sql)
    total = con.execute(f"SELECT COUNT(*) FROM ({query}) __q__").fetchone()[0]
    pages = max(1, (total + page_size - 1) // page_size)
    page = _pagination_page(key, pages)
    offset = (page - 1) * page_size
    df = con.execute(
        f"SELECT * FROM ({query}) __q__ LIMIT {page_size} OFFSET {offset}"
    ).df()
    return df, PageInfo(page, pages, total, page_size)

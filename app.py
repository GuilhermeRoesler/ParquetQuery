#!/usr/bin/env python3
"""Streamlit Parquet Query — exploração de parquets com DuckDB."""

from __future__ import annotations

import streamlit as st

from pq.config import BASE, DATA_DIR
from pq.db.connection import get_connection
from pq.storage import migrate_legacy_dirs
from pq.ui.app_context import build_work_context, render_empty_state
from pq.ui.sidebar import render_sidebar
from pq.ui.state import init_state
from pq.ui.tabs.columns import render_columns_tab
from pq.ui.tabs.explore import render_explore_tab
from pq.ui.tabs.export_tab import render_export_tab
from pq.ui.tabs.sql_tab import render_sql_tab


def main() -> None:
    st.set_page_config(
        page_title="Parquet Query",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    DATA_DIR.mkdir(exist_ok=True)
    migrate_legacy_dirs(DATA_DIR, BASE)

    init_state()
    con = get_connection()

    active, loaded = render_sidebar(con, DATA_DIR)
    if not active:
        render_empty_state()
        return

    ctx = build_work_context(con, DATA_DIR, active, loaded)

    tabs = st.tabs(["Explorar", "SQL", "Colunas", "Exportar"])
    with tabs[0]:
        render_explore_tab(ctx)
    with tabs[1]:
        render_sql_tab(ctx)
    with tabs[2]:
        render_columns_tab(ctx)
    with tabs[3]:
        render_export_tab(ctx)


if __name__ == "__main__":
    main()

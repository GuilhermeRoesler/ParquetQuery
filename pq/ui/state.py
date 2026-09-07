"""Session state Streamlit — sem lógica de SQL derivado."""

from __future__ import annotations

import streamlit as st

from pq.db.cached import clear_overview_cache
from pq.ui.components.pagination import clear_sql_count_cache


def init_state() -> None:
    defaults: dict[str, object] = {
        "loaded_tables": [],
        "derived_by_table": {},
        "last_result_sql": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    st.session_state.pop("derived_select", None)
    st.session_state.pop("working_sql_cache", None)


def get_derived_sql(table: str) -> str | None:
    return st.session_state.derived_by_table.get(table)


def has_derived_sql(table: str) -> bool:
    return table in st.session_state.derived_by_table


def set_derived_sql(table: str, sql: str | None) -> None:
    if sql:
        st.session_state.derived_by_table[table] = sql
    else:
        st.session_state.derived_by_table.pop(table, None)
    clear_overview_cache()
    clear_sql_count_cache()
    st.session_state.pop("sql_editor_ctx", None)

"""Session state Streamlit — sem lógica de SQL derivado."""

from __future__ import annotations

import streamlit as st

from pq.db.cached import clear_overview_cache
from pq.db.schema import describe_sql_cached
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


def get_derived_sql(table: str) -> str | None:
    return st.session_state.derived_by_table.get(table)


def has_derived_sql(table: str) -> bool:
    return table in st.session_state.derived_by_table


def invalidate_data_caches() -> None:
    clear_overview_cache()
    clear_sql_count_cache()
    describe_sql_cached.clear()
    st.session_state.pop("sql_editor_ctx", None)
    st.session_state.pop("sql_table_schemas", None)


def set_derived_sql(table: str, sql: str | None, *, invalidate: bool = True) -> None:
    if sql:
        st.session_state.derived_by_table[table] = sql
    else:
        st.session_state.derived_by_table.pop(table, None)
    if invalidate:
        invalidate_data_caches()

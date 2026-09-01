"""Session state e helpers de SQL derivado."""

from __future__ import annotations

import duckdb
import streamlit as st

from pq.db.cached import clear_overview_cache
from pq.db.derived import (
    build_derived_select,
    default_preview_sql,
    work_from_clause,
    working_sql,
)
from pq.db.sql_utils import strip_sql
from pq.ui.components.pagination import paginate_sql, show_paginated_dataframe


def init_state() -> None:
    defaults = {
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


def work_from(table: str) -> str:
    return work_from_clause(table, get_derived_sql(table))


def build_derived(table: str, select_expr: str) -> str:
    return build_derived_select(table, select_expr, get_derived_sql(table))


def get_working_sql(table: str) -> str:
    return working_sql(table, get_derived_sql(table))


def get_default_preview_sql(table: str, *, limit: int = 100) -> str:
    return default_preview_sql(table, get_derived_sql(table), limit=limit)


def set_derived_sql(table: str, sql: str | None) -> None:
    if sql:
        st.session_state.derived_by_table[table] = sql
    else:
        st.session_state.derived_by_table.pop(table, None)
    clear_overview_cache()
    st.session_state.pop("sql_editor_ctx", None)


def sql_editor_run_requested(editor_response: dict | None, run_btn: bool) -> bool:
    """Botão Executar ou Ctrl+Enter (submit do code_editor, uma vez por id)."""
    if run_btn:
        return True
    if not editor_response or editor_response.get("type") != "submit":
        return False
    submit_id = editor_response.get("id") or ""
    if not submit_id or submit_id == st.session_state.get("sql_last_submit_id"):
        return False
    st.session_state.sql_last_submit_id = submit_id
    return True


def execute_sql_input(con: duckdb.DuckDBPyConnection, sql_text: str) -> None:
    """Executa query na aba SQL (SELECT/WITH paginado; demais comandos direto)."""
    if not sql_text.strip():
        return
    try:
        with st.spinner("Executando..."):
            query = strip_sql(sql_text)
            stripped = query.upper()
            if stripped.startswith("SELECT") or stripped.startswith("WITH"):
                df_sql, sql_info = paginate_sql(con, query, key="sql_page")
                st.session_state.last_result_sql = query
                st.success(f"{sql_info.total:,} linhas no resultado.")
                show_paginated_dataframe(df_sql, sql_info, "sql_page")
            else:
                con.execute(query)
                st.success("Comando executado.")
    except Exception as exc:
        st.error(f"Erro SQL: {exc}")

"""Montagem do contexto de trabalho por rerun."""

from __future__ import annotations

from pathlib import Path

import duckdb
import streamlit as st

from pq.config import is_cloud_mode
from pq.db.derived import work_from_clause, working_sql
from pq.db.schema import describe_sql_cached, get_schema
from pq.storage import base_name_from
from pq.ui.context import WorkContext
from pq.ui.state import get_derived_sql, has_derived_sql


def build_work_context(
    con: duckdb.DuckDBPyConnection,
    data_dir: Path,
    active: str,
    loaded: list[str],
    *,
    cloud_mode: bool | None = None,
) -> WorkContext:
    cloud = is_cloud_mode() if cloud_mode is None else cloud_mode
    derived_sql = get_derived_sql(active)
    schema_df = get_schema(active)
    from_clause = work_from_clause(active, derived_sql)
    work_sql = working_sql(active, derived_sql)

    if derived_sql:
        work_schema_df = describe_sql_cached(derived_sql)
    else:
        work_schema_df = schema_df

    has_derived = has_derived_sql(active)
    sql_editor_ctx = f"{active}:{'derived' if has_derived else 'raw'}"
    if st.session_state.get("sql_editor_ctx") != sql_editor_ctx:
        st.session_state.pop("sql_editor", None)
        st.session_state.sql_editor_ctx = sql_editor_ctx

    return WorkContext(
        con=con,
        data_dir=data_dir,
        active=active,
        loaded=loaded,
        current_base=base_name_from(active),
        schema_df=schema_df,
        work_schema_df=work_schema_df,
        col_names=work_schema_df["column_name"].tolist(),
        col_types=dict(
            zip(
                work_schema_df["column_name"],
                work_schema_df["column_type"],
                strict=True,
            )
        ),
        work_from_clause=from_clause,
        work_sql=work_sql,
        derived_sql=derived_sql,
        has_derived=has_derived,
        cloud_mode=cloud,
    )


def render_empty_state(*, cloud_mode: bool = False) -> None:
    st.title("Parquet Query")
    if cloud_mode:
        st.info(
            "Os datasets de exemplo costumam carregar sozinhos. "
            "Se a sidebar estiver vazia, marque um arquivo e clique **Carregar selecionados**, "
            "ou envie um `.parquet`/`.csv`."
        )
        st.caption(
            "Versão demo online: exportações são feitas por download. "
            "Para versionamento persistente em `data/`, use a [versão local]"
            "(https://github.com/GuilhermeRoesler/ParquetQuery/releases)."
        )
        from pq.ui.demo_recipes import render_demo_recipes_panel

        render_demo_recipes_panel()
    else:
        st.info(
            "Selecione e carregue um arquivo `.parquet` ou `.csv` em `data/` "
            "na barra lateral para começar."
        )

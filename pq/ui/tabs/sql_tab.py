"""Aba SQL — editor, tradutor M e referência."""

from __future__ import annotations

import streamlit as st
from code_editor import code_editor

from pq.db.schema import table_column_names
from pq.translators import (
    ParseError,
    m_parameter_defaults,
    m_parameter_names,
    m_source_table,
    translate_m_to_sql,
)
from pq.ui.components.sql_editor import (
    SQL_EDITOR_COMPONENT_PROPS,
    SQL_EDITOR_OPTIONS,
    SQL_EDITOR_PROPS,
    build_sql_completions,
    inject_sql_editor_layout_css,
)
from pq.ui.context import WorkContext
from pq.ui.state import (
    execute_sql_input,
    get_default_preview_sql,
    get_derived_sql,
    sql_editor_run_requested,
)


def render_sql_tab(ctx: WorkContext) -> None:
    st.header("Editor SQL")
    inject_sql_editor_layout_css()

    default_sql = get_default_preview_sql(ctx.active)

    if isinstance(st.session_state.get("sql_editor"), str):
        st.session_state.sql_editor = {"text": st.session_state.sql_editor}
    if "sql_editor" not in st.session_state:
        st.session_state.sql_editor = {"text": default_sql}

    sql_code = st.session_state.sql_editor.get("text", default_sql)
    table_schemas = {
        table: table_column_names(ctx.con, table, get_derived_sql(table)) for table in ctx.loaded
    }
    sql_completions = build_sql_completions(ctx.loaded, table_schemas)

    st.caption(
        "Sugestões: **Ctrl+Space** · **Ctrl+Enter** executa · "
        "navegue com **↑↓** e confirme com **Enter** ou **Tab**."
    )
    editor_response = code_editor(
        code=sql_code,
        lang="sql",
        height=[14, 22],
        key="sql_editor",
        response_mode=["debounce"],
        options=SQL_EDITOR_OPTIONS,
        props=SQL_EDITOR_PROPS,
        component_props=SQL_EDITOR_COMPONENT_PROPS,
        completions=sql_completions,
    )
    sql_input = (editor_response or st.session_state.sql_editor).get("text", sql_code)

    col_run, _col_clear = st.columns([1, 5])
    run_btn = col_run.button("Executar", type="primary", key="btn_sql_run")

    if sql_editor_run_requested(editor_response, run_btn):
        execute_sql_input(ctx.con, sql_input)

    with st.expander("Tradutor Power Query (M)"):
        m_code = st.text_area(
            "Passos M (Table.SelectRows, TransformColumnTypes, …)",
            height=160,
            key="m_import_code",
            placeholder=(
                "RangeStart = #date(2025, 1, 1),\n"
                "RangeEnd = #date(2026, 1, 1),\n"
                '#"Filtrado" = Table.SelectRows(MinhaTabela, each [DATA] >= RangeStart),'
            ),
        )
        m_src = m_source_table(m_code) if m_code.strip() else None
        if m_src:
            st.caption(f"Tabela de origem detectada no M: `{m_src}`")
        duck_idx = ctx.loaded.index(m_src) if m_src in ctx.loaded else 0
        m_duck_table = st.selectbox(
            "Mapear tabela M → view DuckDB",
            ctx.loaded,
            index=duck_idx,
            key="m_duck_table",
        )
        m_param_values: dict[str, str] = {}
        if m_code.strip():
            try:
                m_params = m_parameter_names(m_code)
                m_defaults = m_parameter_defaults(m_code)
            except ParseError:
                m_params = []
                m_defaults = {}
            if m_params:
                st.markdown("**Parâmetros M** (literal SQL DuckDB)")
                for pname in m_params:
                    default_sql = m_defaults.get(pname, "")
                    m_param_values[pname] = (
                        st.text_input(
                            pname,
                            value=default_sql,
                            placeholder="NULL",
                            key=f"m_param_{pname}",
                            help="Ex.: DATE '2025-01-01', 'texto', 42",
                        ).strip()
                        or "NULL"
                    )
        if st.button("Converter para SQL", key="btn_m_translate"):
            try:
                table_map = {m_src: m_duck_table} if m_src else {}
                st.session_state.m_translated_sql = translate_m_to_sql(
                    m_code,
                    table_map=table_map,
                    param_values=m_param_values or None,
                )
            except ParseError as exc:
                st.warning(f"M inválido ou não suportado: {exc}")
            except Exception as exc:
                st.warning(f"Não foi possível traduzir: {exc}")
        if st.session_state.get("m_translated_sql"):
            st.code(st.session_state.m_translated_sql, language="sql")
            if st.button("Usar no editor", key="btn_m_apply_sql"):
                st.session_state.sql_editor = {"text": st.session_state.m_translated_sql}
                st.rerun()

    with st.expander("Referência rápida — tabelas e exemplos"):
        st.markdown(f"**Tabela ativa:** `{ctx.active}`")
        if ctx.has_derived:
            st.markdown("**Base de trabalho:** inclui colunas calculadas (aba Colunas)")
            st.caption(
                f"Para ver todas as colunas, use `FROM {ctx.work_from_clause}` — "
                f'consultar só `"{ctx.active}"` retorna apenas o arquivo original.'
            )
        st.markdown("**Todas as tabelas carregadas:** " + ", ".join(f"`{t}`" for t in ctx.loaded))
        st.markdown("**Colunas disponíveis:** " + ", ".join(f"`{c}`" for c in ctx.col_names))
        frm = ctx.work_from_clause
        derived_note = (
            "\n-- Com colunas calculadas: use a subquery __work__ (gerada automaticamente)\n"
            if ctx.has_derived
            else ""
        )
        st.code(
            f"""-- Preview{derived_note}
SELECT * FROM {frm} LIMIT 100;

-- Filtrar
SELECT * FROM {frm} WHERE valor > 1000;

-- Agrupar
SELECT categoria, SUM(valor) AS total
FROM {frm}
GROUP BY 1 ORDER BY 2 DESC;
""",
            language="sql",
        )

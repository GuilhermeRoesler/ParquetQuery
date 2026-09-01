"""Aba Colunas — transformações e colunas calculadas."""

from __future__ import annotations

import duckdb
import streamlit as st

from pq.config import CAST_TYPES
from pq.db.sql_utils import quote_ident, validate_derived_sql
from pq.translators import ParseError, normalize_power_formula, translate_power_column
from pq.ui.components.pagination import paginate_sql, show_paginated_dataframe
from pq.ui.context import WorkContext
from pq.ui.state import build_derived, set_derived_sql


def _apply_derived(ctx: WorkContext, new_sql: str, success_msg: str) -> None:
    try:
        validate_derived_sql(ctx.con, new_sql)
        set_derived_sql(ctx.active, new_sql)
        st.success(success_msg)
        st.rerun()
    except duckdb.Error as exc:
        st.error(f"SQL inválido: {exc}")
    except Exception as exc:
        st.error(f"Erro: {exc}")


def render_columns_tab(ctx: WorkContext) -> None:
    st.header("Transformar Colunas")

    derived_cols = ctx.col_names

    op = st.radio(
        "Operação",
        ["Adicionar coluna calculada", "Renomear coluna", "Remover colunas", "Cast de tipo"],
        horizontal=True,
        key="col_op",
    )

    if op == "Adicionar coluna calculada":
        expr_mode = st.radio(
            "Tipo de expressão",
            ["DuckDB", "Power BI (DAX)"],
            horizontal=True,
            key="col_expr_mode",
            help="Cole fórmulas de colunas calculadas do Power BI / DAX (ex.: IF, FORMAT, TODAY).",
        )

        if expr_mode == "DuckDB":
            new_col_name = st.text_input("Nome da nova coluna", key="new_col_name")
            new_col_expr = st.text_input(
                "Expressão DuckDB",
                placeholder=f"{quote_ident(derived_cols[0])} * 2",
                key="new_col_expr",
            )
            if st.button("Adicionar", key="btn_add_col"):
                if new_col_name and new_col_expr:
                    new_sql = build_derived(
                        ctx.active,
                        f"*, ({new_col_expr}) AS {quote_ident(new_col_name)}",
                    )
                    _apply_derived(ctx, new_sql, f"Coluna `{new_col_name}` adicionada.")
        else:
            with st.expander("Exemplos de fórmulas Power BI (DAX)"):
                st.code(
                    """Dias em Atraso = FORMAT(TODAY()- 'fValorNotas'[VENCIMENTO_PARCELA].[Date], 0)

Aging_Atual = IF('fValorNotas'[Dias em Atraso]>360,"9_Acima 361",
    IF('fValorNotas'[Dias em Atraso]>180,"8_181 - 360",
    IF('fValorNotas'[Dias em Atraso]>0,"2_01 - 30","1_A vencer")))""",
                    language="text",
                )
                st.caption(
                    "Use o formato `Nome = expressão`. Referências `'Tabela'[Coluna]` ou `[Coluna]` "
                    "são mapeadas para as colunas da view atual. Suporta IF, VAR/RETURN, comentários `--`, "
                    "SUBSTITUTE, FIND, SEARCH, TRIM, LEFT, FORMAT, TODAY, `.[Date]`, etc."
                )

            pq_formula = st.text_area(
                "Fórmula Power BI (DAX)",
                height=140,
                key="pq_col_formula",
                placeholder='Minha Coluna = IF([valor] > 100, "Alto", "Baixo")',
            )

            if pq_formula.strip():
                try:
                    col_name, duck_expr = translate_power_column(
                        normalize_power_formula(pq_formula)
                    )
                    st.caption(f"Traduzido para DuckDB — coluna `{col_name}`:")
                    st.code(duck_expr, language="sql")
                except ParseError as exc:
                    st.warning(f"Fórmula inválida: {exc}")
                except Exception as exc:
                    st.warning(f"Não foi possível traduzir: {exc}")

            if st.button("Adicionar fórmula", key="btn_add_pq_col"):
                if not pq_formula.strip():
                    st.warning("Cole uma fórmula no formato: Nome da Coluna = expressão")
                else:
                    try:
                        col_name, duck_expr = translate_power_column(
                            normalize_power_formula(pq_formula)
                        )
                        new_sql = build_derived(
                            ctx.active,
                            f"*, ({duck_expr}) AS {quote_ident(col_name)}",
                        )
                        _apply_derived(
                            ctx,
                            new_sql,
                            f"Coluna `{col_name}` adicionada via fórmula Power BI.",
                        )
                    except ParseError as exc:
                        st.error(f"Fórmula inválida: {exc}")

    elif op == "Renomear coluna":
        rename_src = st.selectbox("Coluna original", derived_cols, key="rename_src")
        rename_dst = st.text_input("Novo nome", key="rename_dst")
        if st.button("Renomear", key="btn_rename"):
            if rename_dst:
                col_list = ", ".join(
                    f"{quote_ident(c)} AS {quote_ident(rename_dst)}"
                    if c == rename_src
                    else quote_ident(c)
                    for c in derived_cols
                )
                new_sql = build_derived(ctx.active, col_list)
                _apply_derived(ctx, new_sql, f"`{rename_src}` renomeada para `{rename_dst}`.")

    elif op == "Remover colunas":
        drop_cols = st.multiselect("Colunas a remover", derived_cols, key="drop_cols")
        if st.button("Remover", key="btn_drop"):
            if drop_cols:
                keep = [c for c in derived_cols if c not in drop_cols]
                col_list = ", ".join(quote_ident(c) for c in keep)
                new_sql = build_derived(ctx.active, col_list)
                _apply_derived(ctx, new_sql, f"{len(drop_cols)} coluna(s) removida(s).")

    elif op == "Cast de tipo":
        cast_col = st.selectbox("Coluna", derived_cols, key="cast_col")
        cast_type = st.selectbox("Tipo destino", CAST_TYPES, key="cast_type")
        if st.button("Aplicar cast", key="btn_cast"):
            col_list = ", ".join(
                f"TRY_CAST({quote_ident(c)} AS {cast_type}) AS {quote_ident(c)}"
                if c == cast_col
                else quote_ident(c)
                for c in derived_cols
            )
            new_sql = build_derived(ctx.active, col_list)
            _apply_derived(ctx, new_sql, f"`{cast_col}` convertida para `{cast_type}`.")

    st.markdown("---")

    current_sql = st.session_state.derived_by_table.get(ctx.active)
    if current_sql:
        with st.expander("SQL da view derivada atual"):
            st.code(current_sql, language="sql")

        c1, c2 = st.columns(2)
        if c1.button("Pré-visualizar resultado", key="btn_preview_derived"):
            try:
                df_der, der_info = paginate_sql(ctx.con, current_sql, key="derived_page")
                st.session_state.last_result_sql = current_sql
                st.success(f"{der_info.total:,} linhas.")
                show_paginated_dataframe(df_der, der_info, "derived_page")
            except duckdb.Error as exc:
                st.error(f"Erro SQL: {exc}")

        if c2.button("Resetar transformações", key="btn_reset_derived"):
            set_derived_sql(ctx.active, None)
            st.rerun()
    else:
        st.info("Nenhuma transformação aplicada. Use as opções acima.")

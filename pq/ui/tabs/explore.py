"""Aba Explorar — schema, preview e overview."""

from __future__ import annotations

import streamlit as st

from pq.config import OVERVIEW_AGGS
from pq.db.cached import get_classificatory_overview, get_numeric_overview
from pq.overview.format_pt import format_number_pt
from pq.overview.sql import build_classificatory_overview_sql, build_numeric_overview_sql
from pq.ui.components.pagination import paginate, paginate_sql, show_paginated_dataframe
from pq.ui.context import WorkContext


def render_explore_tab(ctx: WorkContext) -> None:
    st.header(f"Explorar — {ctx.active}")
    if ctx.has_derived:
        st.caption("Exibindo tabela com colunas calculadas da aba Colunas.")

    subtab_schema, subtab_preview, subtab_overview = st.tabs(
        ["Schema", "Preview", "Overview de valores"]
    )

    with subtab_schema:
        st.dataframe(ctx.work_schema_df, use_container_width=True, hide_index=True)
        if ctx.has_derived:
            with st.expander("Schema original do arquivo"):
                st.dataframe(ctx.schema_df, use_container_width=True, hide_index=True)

    with subtab_preview:
        preview_cols = st.multiselect(
            "Colunas a exibir (vazio = todas)",
            ctx.col_names,
            key="preview_cols",
        )
        cols_expr = ", ".join(f'"{c}"' for c in preview_cols) if preview_cols else "*"
        preview_sql = f"SELECT {cols_expr} FROM {ctx.work_from_clause}"
        df_preview, preview_info = paginate_sql(ctx.con, preview_sql, key="preview_page")
        show_paginated_dataframe(df_preview, preview_info, "preview_page")

    with subtab_overview:
        overview_mode = st.radio(
            "Tipo de overview",
            ["Classificatório", "Numérico"],
            horizontal=True,
            key="overview_mode",
        )
        overview_col = st.selectbox("Coluna", ctx.col_names, key="overview_col")
        overview_dtype = ctx.col_types.get(overview_col, "VARCHAR")

        if overview_mode == "Numérico":
            overview_agg = st.selectbox("Agregação", OVERVIEW_AGGS, key="overview_agg")
            overview_sql = build_numeric_overview_sql(
                ctx.active, overview_col, overview_agg, overview_dtype, ctx.derived_sql
            )
        else:
            overview_agg = None
            overview_sql = build_classificatory_overview_sql(
                ctx.active, overview_col, ctx.derived_sql
            )

        with st.expander("SQL gerado"):
            st.code(overview_sql, language="sql")

        if st.button("Calcular overview", type="primary", key="btn_value_overview"):
            try:
                if overview_mode == "Classificatório":
                    with st.spinner("Calculando frequências..."):
                        df_overview = get_classificatory_overview(
                            ctx.active, overview_col, ctx.derived_sql
                        )
                        distinct_count = len(df_overview)
                        total_rows = (
                            int(df_overview["quantidade"].sum()) if not df_overview.empty else 0
                        )
                        st.success(
                            f"{distinct_count:,} valor(es) distinto(s) · {total_rows:,} linhas contabilizadas"
                        )
                        df_overview_page, overview_info = paginate(
                            df_overview, key="overview_page", page_size=100
                        )
                        show_paginated_dataframe(df_overview_page, overview_info, "overview_page")
                else:
                    with st.spinner("Calculando agregação..."):
                        result = get_numeric_overview(
                            ctx.active,
                            overview_col,
                            overview_agg,
                            overview_dtype,
                            ctx.derived_sql,
                        )
                        formatted = format_number_pt(result)
                        st.markdown(
                            f"<p style='font-size:2.25rem;font-weight:600;margin:0.5rem 0'>"
                            f"{formatted}</p>",
                            unsafe_allow_html=True,
                        )
                        st.caption(f"{overview_agg} · `{overview_col}`")
            except Exception as exc:
                st.error(f"Erro ao calcular overview: {exc}")

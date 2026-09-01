"""Barra lateral — carregamento de arquivos e tabela ativa."""

from __future__ import annotations

from pathlib import Path

import duckdb
import streamlit as st

from pq.config import LOADABLE_EXTENSIONS
from pq.db.cached import clear_overview_cache
from pq.db.connection import register_view
from pq.db.queries import count_from_sql
from pq.db.schema import count_rows, get_schema
from pq.storage import (
    base_name_from,
    build_timeline,
    format_bytes,
    list_data_files,
    version_from_stem,
)
from pq.ui.state import has_derived_sql, set_derived_sql, work_from


def render_sidebar(
    con: duckdb.DuckDBPyConnection,
    data_dir: Path,
) -> tuple[str | None, list[str]]:
    with st.sidebar:
        st.title("⚡ Parquet Query")
        st.caption("Dados versionados em `data/`")
        st.markdown("---")

        data_files = [
            path
            for path in list_data_files(data_dir)
            if path.suffix.lower() in LOADABLE_EXTENSIONS
        ]

        if not data_files:
            st.warning("Nenhum `.parquet` ou `.csv` encontrado em `data/`.")
        else:
            st.subheader("Bases disponíveis")
            selected: list[Path] = []
            for df_path in data_files:
                size = format_bytes(df_path.stat().st_size)
                version = version_from_stem(df_path.stem)
                version_label = "original" if version is None else f"v{version}"
                fmt_label = df_path.suffix.lower().lstrip(".")
                checked = st.checkbox(
                    f"{df_path.stem}  `{size}`  · {version_label} · {fmt_label}",
                    key=f"chk_{df_path.name}",
                )
                if checked:
                    selected.append(df_path)

            if st.button("Carregar selecionados", type="primary", disabled=not selected):
                for df_path in selected:
                    register_view(con, df_path.stem, df_path)
                    if df_path.stem not in st.session_state.loaded_tables:
                        st.session_state.loaded_tables.append(df_path.stem)
                    set_derived_sql(df_path.stem, None)
                get_schema.clear()
                count_rows.clear()
                clear_overview_cache()
                st.success(f"{len(selected)} tabela(s) carregada(s).")
                st.rerun()

        st.markdown("---")
        loaded = st.session_state.loaded_tables
        if loaded:
            st.subheader("Tabela ativa")
            active = st.selectbox("Selecionar tabela", loaded, key="active_table")
            if active:
                current_base = base_name_from(active)
                row_count = count_from_sql(con, work_from(active))
                st.caption(f"Base: `{current_base}` · {row_count:,} linhas")
                if has_derived_sql(active):
                    st.caption("Colunas calculadas ativas")

                timeline = build_timeline(data_dir, current_base)
                if timeline:
                    with st.expander("Timeline de versões", expanded=False):
                        for item in timeline:
                            files = ", ".join(f"`{f.name}`" for f in item["files"]) or "—"
                            meta = item.get("meta") or {}
                            updated = meta.get("updated_at") or meta.get("created_at")
                            when = f" · {updated[:16].replace('T', ' ')}" if updated else ""
                            st.markdown(f"**{item['label']}** — {files}{when}")
            return active, loaded

        st.info("Carregue ao menos um arquivo.")
        return None, loaded

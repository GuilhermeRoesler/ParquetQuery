"""Barra lateral — carregamento de arquivos e tabela ativa."""

from __future__ import annotations

from pathlib import Path

import duckdb
import streamlit as st

from pq.config import LOADABLE_EXTENSIONS, is_cloud_mode
from pq.db.cached import clear_overview_cache
from pq.db.connection import register_view
from pq.db.queries import count_from_sql
from pq.db.schema import get_schema
from pq.storage import (
    base_name_from,
    build_timeline,
    format_bytes,
    list_data_files,
    load_manifest,
    manifest_corrupt_message,
    manifest_is_corrupt,
    version_from_stem,
)
from pq.storage.cloud import (
    cloud_upload_dir,
    list_cloud_sources,
    process_sidebar_uploads,
)
from pq.ui.components.pagination import clear_sql_count_cache
from pq.ui.state import has_derived_sql, set_derived_sql, work_from


def _load_paths(con: duckdb.DuckDBPyConnection, paths: list[Path]) -> None:
    for df_path in paths:
        register_view(con, df_path.stem, df_path)
        if df_path.stem not in st.session_state.loaded_tables:
            st.session_state.loaded_tables.append(df_path.stem)
        set_derived_sql(df_path.stem, None)
    get_schema.clear()
    clear_overview_cache()
    clear_sql_count_cache()


def _render_active_table(
    con: duckdb.DuckDBPyConnection, data_dir: Path
) -> tuple[str | None, list[str]]:
    loaded = st.session_state.loaded_tables
    if not loaded:
        st.info("Carregue ao menos um arquivo.")
        return None, loaded

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


def _render_local_file_picker(
    con: duckdb.DuckDBPyConnection,
    data_dir: Path,
) -> tuple[str | None, list[str]]:
    manifest = load_manifest(data_dir)
    if manifest_is_corrupt(manifest):
        st.warning(
            f"`_manifest.json` corrompido ou inválido: {manifest_corrupt_message(manifest)}. "
            "Metadados de versão podem estar incompletos até a próxima exportação."
        )

    data_files = [
        path for path in list_data_files(data_dir) if path.suffix.lower() in LOADABLE_EXTENSIONS
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
            _load_paths(con, selected)
            st.success(f"{len(selected)} tabela(s) carregada(s).")
            st.rerun()

    st.markdown("---")
    return _render_active_table(con, data_dir)


def _render_cloud_file_picker(
    con: duckdb.DuckDBPyConnection,
    data_dir: Path,
) -> tuple[str | None, list[str]]:
    st.caption("Modo demo online — dados não persistem entre sessões.")
    st.markdown(
        "[Versão local completa](https://github.com/GuilhermeRoesler/ParquetQuery/releases) "
        "com versionamento em disco."
    )

    upload_dir = cloud_upload_dir()
    saved = process_sidebar_uploads(upload_dir)
    if saved:
        st.success(f"{saved} arquivo(s) recebido(s).")
        st.rerun()

    st.file_uploader(
        "Enviar `.parquet` ou `.csv` (até 50 MB)",
        type=["parquet", "csv"],
        accept_multiple_files=True,
        key="cloud_file_uploader",
    )

    sources = list_cloud_sources(upload_dir)
    if not sources:
        st.info("Envie um arquivo ou carregue o dataset de exemplo abaixo.")
    else:
        st.subheader("Arquivos disponíveis")
        selected: list[Path] = []
        for df_path, source_label in sources:
            size = format_bytes(df_path.stat().st_size)
            fmt_label = df_path.suffix.lower().lstrip(".")
            checked = st.checkbox(
                f"{df_path.stem}  `{size}`  · {source_label} · {fmt_label}",
                key=f"chk_{df_path.name}_{source_label}",
            )
            if checked:
                selected.append(df_path)

        if st.button("Carregar selecionados", type="primary", disabled=not selected):
            _load_paths(con, selected)
            st.success(f"{len(selected)} tabela(s) carregada(s).")
            st.rerun()

    st.markdown("---")
    return _render_active_table(con, data_dir)


def render_sidebar(
    con: duckdb.DuckDBPyConnection,
    data_dir: Path,
    *,
    cloud_mode: bool | None = None,
) -> tuple[str | None, list[str]]:
    cloud = is_cloud_mode() if cloud_mode is None else cloud_mode
    with st.sidebar:
        st.title("⚡ Parquet Query")
        if cloud:
            st.caption("Experimente online · Parquet Query")
        else:
            st.caption("Dados versionados em `data/`")
        st.markdown("---")

        if cloud:
            return _render_cloud_file_picker(con, data_dir)
        return _render_local_file_picker(con, data_dir)

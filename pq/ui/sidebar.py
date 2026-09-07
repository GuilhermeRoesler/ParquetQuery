"""Barra lateral — carregamento de arquivos e tabela ativa."""

from __future__ import annotations

from pathlib import Path

import duckdb
import streamlit as st

from pq.config import LOADABLE_EXTENSIONS, is_cloud_mode
from pq.db.connection import register_view
from pq.db.derived import working_sql
from pq.db.schema import get_schema
from pq.storage import (
    base_name_from,
    build_timeline,
    format_bytes,
    list_data_files,
    version_from_stem,
)
from pq.storage.cloud import (
    cloud_upload_dir,
    list_cloud_sources,
    list_demo_files,
    process_sidebar_uploads,
)
from pq.ui.components.manifest import warn_if_manifest_corrupt
from pq.ui.components.pagination import cached_sql_count
from pq.ui.state import get_derived_sql, has_derived_sql, invalidate_data_caches, set_derived_sql


def _load_paths(con: duckdb.DuckDBPyConnection, paths: list[Path]) -> None:
    for df_path in paths:
        register_view(con, df_path.stem, df_path)
        if df_path.stem not in st.session_state.loaded_tables:
            st.session_state.loaded_tables.append(df_path.stem)
        set_derived_sql(df_path.stem, None, invalidate=False)
    get_schema.clear()
    invalidate_data_caches()


def _render_file_checklist(
    items: list[tuple[Path, str]],
    *,
    key_prefix: str,
    label_as_title: bool = False,
) -> list[Path]:
    """Checklist compartilhado cloud/local; cada item é (path, rótulo extra)."""
    selected: list[Path] = []
    for df_path, extra_label in items:
        size = format_bytes(df_path.stat().st_size)
        fmt_label = df_path.suffix.lower().lstrip(".")
        if label_as_title:
            title = f"{extra_label}  `{size}`  · {fmt_label}"
        else:
            title = f"{df_path.stem}  `{size}`  · {extra_label} · {fmt_label}"
        checked = st.checkbox(
            title,
            key=f"{key_prefix}{df_path.name}",
        )
        if checked:
            selected.append(df_path)
    return selected


def _prefer_originals(paths: list[Path]) -> list[Path]:
    """Originais (sem `_vN`) primeiro — útil no auto-load local."""
    return sorted(
        paths,
        key=lambda p: (0 if version_from_stem(p.stem) is None else 1, p.name),
    )


def _render_glossary() -> None:
    with st.expander("Glossário", expanded=False):
        st.markdown(
            "- **Tabela** — arquivo carregado no DuckDB (nome = stem do arquivo)\n"
            "- **Base** — nome sem sufixo de versão (`vendas` em `vendas_v2`)\n"
            "- **Versão** — exportação em `data/` como `{base}_vN`\n"
            "- **Colunas calculadas** — transformações da aba Colunas "
            "(não alteram o arquivo no disco)"
        )


def _render_active_table(
    con: duckdb.DuckDBPyConnection, data_dir: Path
) -> tuple[str | None, list[str]]:
    loaded = st.session_state.loaded_tables
    if not loaded:
        st.info("Abra um arquivo acima para começar.")
        return None, loaded

    st.subheader("Tabela ativa")
    active = st.selectbox("Selecionar tabela", loaded, key="active_table")
    if active:
        current_base = base_name_from(active)
        derived = get_derived_sql(active)
        row_count = cached_sql_count(
            con,
            working_sql(active, derived),
            cache_key=f"sidebar_{active}",
        )
        st.caption(f"Base: `{current_base}` · {row_count:,} linhas")
        if has_derived_sql(active):
            st.badge("Colunas calculadas ativas", color="orange")
            st.caption("Exportações e o preview usam estas transformações.")

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


def _render_open_button(con: duckdb.DuckDBPyConnection, selected: list[Path]) -> None:
    """Botão único: 'Abrir arquivo' (1) ou 'Carregar selecionados' (vários)."""
    n = len(selected)
    label = "Abrir arquivo" if n <= 1 else f"Carregar selecionados ({n})"
    if st.button(label, type="primary", disabled=not selected, key="btn_open_files"):
        _load_paths(con, selected)
        st.toast(f"{n} tabela(s) aberta(s).")
        st.rerun()


def _render_local_file_picker(
    con: duckdb.DuckDBPyConnection,
    data_dir: Path,
) -> tuple[str | None, list[str]]:
    warn_if_manifest_corrupt(data_dir)

    data_files = [
        path for path in list_data_files(data_dir) if path.suffix.lower() in LOADABLE_EXTENSIONS
    ]

    # Primeira visita local: abre o primeiro original disponível sem clique.
    if not st.session_state.get("local_autoload_done"):
        st.session_state.local_autoload_done = True
        if data_files and not st.session_state.loaded_tables:
            first = _prefer_originals(data_files)[:1]
            _load_paths(con, first)
            st.toast(f"Arquivo aberto: `{first[0].stem}`")
            st.rerun()

    if not data_files:
        st.warning("Nenhum `.parquet` ou `.csv` encontrado em `data/`.")
    else:
        st.subheader("Arquivos em data/")
        items = []
        for path in data_files:
            ver = version_from_stem(path.stem)
            items.append((path, "original" if ver is None else f"v{ver}"))
        selected = _render_file_checklist(items, key_prefix="chk_")
        _render_open_button(con, selected)

    st.markdown("---")
    active, loaded = _render_active_table(con, data_dir)
    _render_glossary()
    return active, loaded


def _render_cloud_file_picker(
    con: duckdb.DuckDBPyConnection,
    data_dir: Path,
) -> tuple[str | None, list[str]]:
    st.caption("Modo demo online — dados não persistem entre sessões.")
    st.markdown(
        "[Versão local completa](https://github.com/GuilhermeRoesler/ParquetQuery/releases) "
        "com versionamento em disco."
    )

    # Primeira visita: carrega os datasets de exemplo sem clique.
    if not st.session_state.get("cloud_demo_autoload_done"):
        st.session_state.cloud_demo_autoload_done = True
        demo_paths = list_demo_files()
        # vendas_demo primeiro → vira tabela ativa inicial no selectbox
        demo_paths = sorted(
            demo_paths,
            key=lambda p: (0 if p.stem == "vendas_demo" else 1, p.name),
        )
        if demo_paths and not st.session_state.loaded_tables:
            _load_paths(con, demo_paths)
            st.toast("Datasets de exemplo carregados.")
            st.rerun()

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
        st.info("Envie um arquivo ou use o dataset de exemplo abaixo.")
    else:
        st.subheader("Arquivos disponíveis")
        selected = _render_file_checklist(sources, key_prefix="chk_", label_as_title=True)
        _render_open_button(con, selected)

    st.markdown("---")
    active, loaded = _render_active_table(con, data_dir)
    _render_glossary()
    return active, loaded


def render_sidebar(
    con: duckdb.DuckDBPyConnection,
    data_dir: Path,
    *,
    cloud_mode: bool | None = None,
) -> tuple[str | None, list[str]]:
    cloud = is_cloud_mode() if cloud_mode is None else cloud_mode
    with st.sidebar:
        st.title("Parquet Query")
        if cloud:
            st.caption("Experimente online · Parquet Query")
        else:
            st.caption("Dados versionados em `data/`")
        st.markdown("---")

        if cloud:
            return _render_cloud_file_picker(con, data_dir)
        return _render_local_file_picker(con, data_dir)

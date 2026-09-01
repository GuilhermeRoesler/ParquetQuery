"""Aba Exportar — download e versionamento em data/."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pq.config import LIMITE_XLSX, LOADABLE_EXTENSIONS
from pq.db.connection import run_query
from pq.export.io import export_extension, export_to_bytes, save_to_data
from pq.storage import (
    build_timeline,
    files_for_version,
    list_version_numbers,
    load_manifest,
    next_available_version,
    record_version,
    versioned_stem,
)
from pq.ui.context import WorkContext


def render_export_tab(ctx: WorkContext) -> None:
    st.header("Exportar")
    st.caption(f"Base de dados: `{ctx.current_base}` · destino padrão: `data/`")

    export_source = st.radio(
        "O que exportar?",
        [
            "Tabela com colunas calculadas",
            "Último resultado (SQL)",
            "Somente arquivo original",
        ],
        key="export_source",
    )

    if export_source == "Tabela com colunas calculadas":
        export_sql = ctx.work_sql
    elif export_source == "Último resultado (SQL)":
        if st.session_state.last_result_sql:
            export_sql = st.session_state.last_result_sql
        else:
            st.warning("Nenhum resultado encontrado. Execute uma query na aba SQL primeiro.")
            st.stop()
    else:
        export_sql = f'SELECT * FROM "{ctx.active}"'

    with st.expander("SQL que será exportado"):
        st.code(export_sql, language="sql")

    timeline = build_timeline(ctx.data_dir, ctx.current_base)
    existing_versions = list_version_numbers(ctx.data_dir, ctx.current_base)
    next_version = next_available_version(ctx.data_dir, ctx.current_base)

    col_timeline, col_config = st.columns([1.2, 1])
    with col_timeline:
        st.subheader("Timeline")
        if timeline:
            rows = []
            for item in timeline:
                files = ", ".join(f.name for f in item["files"])
                meta = item.get("meta") or {}
                rows.append(
                    {
                        "Versão": item["label"],
                        "Arquivo(s)": files or "—",
                        "Formato": meta.get("format", "—"),
                        "Origem": meta.get("export_source", "—"),
                        "Atualizado": (meta.get("updated_at") or meta.get("created_at") or "—")[
                            :16
                        ].replace("T", " "),
                    }
                )
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma versão registrada ainda. A primeira exportação será `_v1`.")

    with col_config:
        st.subheader("Versionamento")
        export_fmt = st.radio("Formato", ["Parquet", "CSV", "XLSX"], horizontal=True, key="export_fmt")
        version_mode = st.radio(
            "Modo",
            ["Nova versão", "Sobrescrever versão"],
            horizontal=True,
            key="export_version_mode",
        )

        if version_mode == "Nova versão":
            export_version = next_version
            suggested_stem = versioned_stem(ctx.current_base, export_version)
            st.caption(f"Próxima versão disponível: **v{export_version}**")
        else:
            if not existing_versions:
                st.warning("Não há versões `_vN` para sobrescrever.")
                export_version = next_version
                suggested_stem = versioned_stem(ctx.current_base, export_version)
            else:
                export_version = st.selectbox(
                    "Versão existente",
                    existing_versions,
                    format_func=lambda v: f"v{v}",
                    key="export_overwrite_version",
                )
                suggested_stem = versioned_stem(ctx.current_base, export_version)
                existing_files = files_for_version(ctx.data_dir, ctx.current_base, export_version)
                if existing_files:
                    st.warning(
                        "Sobrescrever substitui: "
                        + ", ".join(f"`{f.name}`" for f in existing_files)
                    )

        defaults_key = f"{ctx.current_base}:{version_mode}:{export_version}:{export_fmt}"
        if st.session_state.get("export_defaults_key") != defaults_key:
            st.session_state.export_filename = suggested_stem
            st.session_state.export_defaults_key = defaults_key

        export_filename = st.text_input(
            "Nome do arquivo (sem extensão)",
            key="export_filename",
        )

        manifest = load_manifest(ctx.data_dir)
        version_meta = (
            manifest.get("bases", {})
            .get(ctx.current_base, {})
            .get("versions", {})
            .get(str(export_version))
        )
        if version_meta:
            with st.expander("Configuração da versão selecionada"):
                st.json(version_meta)

    overwrite = version_mode == "Sobrescrever versão" and bool(existing_versions)
    dest_path = ctx.data_dir / f"{export_filename}.{export_extension(export_fmt)}"
    st.caption(f"Destino: `{dest_path}`")

    col_dl, col_save = st.columns(2)

    if col_dl.button("Baixar arquivo", type="primary", key="btn_download"):
        try:
            with st.spinner("Preparando arquivo..."):
                df_exp = run_query(ctx.con, export_sql)

                if export_fmt == "XLSX" and len(df_exp) > LIMITE_XLSX:
                    st.warning(
                        f"O resultado tem {len(df_exp):,} linhas. O Excel suporta até {LIMITE_XLSX:,}. "
                        "Apenas as primeiras serão exportadas."
                    )
                    df_exp = df_exp.head(LIMITE_XLSX)

                fname = f"{export_filename}.{export_extension(export_fmt)}"
                data, mime = export_to_bytes(df_exp, export_fmt)

                st.download_button(
                    label=f"Clique para baixar {fname}",
                    data=data,
                    file_name=fname,
                    mime=mime,
                    key="dl_btn",
                )
        except Exception as exc:
            st.error(f"Erro ao exportar: {exc}")

    if col_save.button("Salvar em data/", key="btn_save_data"):
        try:
            with st.spinner("Salvando..."):
                df_exp = run_query(ctx.con, export_sql)

                if export_fmt == "XLSX" and len(df_exp) > LIMITE_XLSX:
                    df_exp = df_exp.head(LIMITE_XLSX)
                    st.warning(f"Exportado com limite de {LIMITE_XLSX:,} linhas.")

                if overwrite:
                    for old_file in files_for_version(ctx.data_dir, ctx.current_base, export_version):
                        if old_file != dest_path:
                            old_file.unlink()

                dest = save_to_data(df_exp, dest_path, export_fmt, overwrite=overwrite)
                record_version(
                    ctx.data_dir,
                    ctx.current_base,
                    export_version,
                    filename=dest.name,
                    fmt=export_fmt,
                    source_table=ctx.active,
                    export_source=export_source,
                    overwrite=overwrite,
                )
                st.success(f"Versão salva em `{dest}`")
                if (
                    dest.suffix.lower() in LOADABLE_EXTENSIONS
                    and dest.stem not in st.session_state.loaded_tables
                ):
                    st.caption(
                        "Recarregue o arquivo na barra lateral para trabalhar com esta versão."
                    )
                st.rerun()
        except FileExistsError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Erro ao salvar: {exc}")

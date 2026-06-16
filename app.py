#!/usr/bin/env python3
"""Streamlit Parquet Query — exploração de parquets com DuckDB."""

from __future__ import annotations

import io
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from data_store import (
    base_name_from,
    build_timeline,
    files_for_version,
    list_data_files,
    list_version_numbers,
    load_manifest,
    migrate_legacy_dirs,
    next_available_version,
    record_version,
    version_from_stem,
    versioned_stem,
)
from pq_dax_translator import ParseError, normalize_power_formula, translate_power_column

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent
DATA_DIR = BASE / "data"
DATA_DIR.mkdir(exist_ok=True)
migrate_legacy_dirs(DATA_DIR, BASE)

AGGS = ["SUM", "AVG", "COUNT", "COUNT DISTINCT", "MIN", "MAX", "FIRST", "LAST"]
CAST_TYPES = ["VARCHAR", "INTEGER", "BIGINT", "DOUBLE", "BOOLEAN", "DATE", "TIMESTAMP"]
LIMITE_XLSX = 1_048_576

st.set_page_config(
    page_title="Parquet Query",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# DuckDB connection (singleton — criada uma única vez por sessão do servidor)
# ---------------------------------------------------------------------------
@st.cache_resource
def get_con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


con = get_con()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def register_view(name: str, path: Path) -> None:
    con.execute(f'CREATE OR REPLACE VIEW "{name}" AS SELECT * FROM read_parquet(\'{path.as_posix()}\')')


def list_views() -> list[str]:
    return [r[0] for r in con.execute("SHOW TABLES").fetchall()]


@st.cache_data(ttl=300)
def get_schema(table: str) -> pd.DataFrame:
    return con.execute(f'DESCRIBE "{table}"').df()


@st.cache_data(ttl=300)
def get_summarize(table: str) -> pd.DataFrame:
    return con.execute(f'SUMMARIZE "{table}"').df()


@st.cache_data(ttl=300)
def count_rows(table: str) -> int:
    return con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


def build_value_overview_sql(base_sql: str, col: str) -> str:
    return (
        f'SELECT "{col}", COUNT(*) AS "quantidade"\n'
        f'FROM ({base_sql}) __base__\n'
        f'GROUP BY "{col}"\n'
        f'ORDER BY "quantidade" DESC'
    )


@st.cache_data(ttl=300)
def get_value_overview(base_sql: str, col: str) -> pd.DataFrame:
    return con.execute(build_value_overview_sql(base_sql, col)).df()


def get_distinct_values(base_sql: str, col: str, limit: int = 500) -> list:
    rows = con.execute(
        f'SELECT DISTINCT "{col}" FROM ({base_sql}) __base__ '
        f'WHERE "{col}" IS NOT NULL ORDER BY 1 LIMIT {limit}'
    ).fetchall()
    return [r[0] for r in rows]


@st.cache_data(ttl=300)
def get_summarize_for(base_sql: str) -> pd.DataFrame:
    return con.execute(f"SUMMARIZE ({base_sql})").df()


def count_rows_sql(base_sql: str) -> int:
    return con.execute(f"SELECT COUNT(*) FROM ({base_sql}) __base__").fetchone()[0]


def run_query(sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


def paginate(df: pd.DataFrame, key: str, page_size: int = 500) -> pd.DataFrame:
    total = len(df)
    pages = max(1, (total + page_size - 1) // page_size)
    if pages == 1:
        return df
    page = st.number_input(
        f"Página (de {pages}, {total:,} linhas)",
        min_value=1,
        max_value=pages,
        value=1,
        step=1,
        key=key,
    )
    return df.iloc[(page - 1) * page_size : page * page_size]


def paginate_sql(sql: str, key: str, page_size: int = 500) -> tuple[pd.DataFrame, int]:
    """Paginação diretamente no DuckDB — não carrega tudo na RAM."""
    total = con.execute(f"SELECT COUNT(*) FROM ({sql}) __q__").fetchone()[0]
    pages = max(1, (total + page_size - 1) // page_size)
    page = st.number_input(
        f"Página (de {pages:,}, {total:,} linhas totais)",
        min_value=1,
        max_value=pages,
        value=1,
        step=1,
        key=key,
    )
    offset = (page - 1) * page_size
    df = con.execute(f"SELECT * FROM ({sql}) __q__ LIMIT {page_size} OFFSET {offset}").df()
    return df, total


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def df_to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    return buf.getvalue()


def df_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    return buf.getvalue()


def export_extension(fmt: str) -> str:
    return {"CSV": "csv", "XLSX": "xlsx", "Parquet": "parquet"}[fmt]


def export_to_bytes(df: pd.DataFrame, fmt: str) -> tuple[bytes, str]:
    if fmt == "CSV":
        return df_to_csv_bytes(df), "text/csv"
    if fmt == "Parquet":
        return df_to_parquet_bytes(df), "application/vnd.apache.parquet"
    return df_to_xlsx_bytes(df), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def save_to_data(
    df: pd.DataFrame,
    dest: Path,
    fmt: str,
    *,
    overwrite: bool,
) -> Path:
    if dest.exists() and not overwrite:
        raise FileExistsError(f"O arquivo `{dest.name}` já existe.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "CSV":
        df.to_csv(dest, index=False, encoding="utf-8-sig")
    elif fmt == "Parquet":
        df.to_parquet(dest, index=False, engine="pyarrow")
    else:
        df.to_excel(dest, index=False, engine="openpyxl")
    return dest


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
def _init_state() -> None:
    defaults = {
        "loaded_tables": [],
        "filters": [],
        "derived_by_table": {},
        "last_result_sql": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    st.session_state.pop("derived_select", None)
    st.session_state.pop("working_sql_cache", None)


def working_sql(table: str) -> str:
    derived = st.session_state.derived_by_table.get(table)
    if derived:
        return derived
    return f'SELECT * FROM "{table}"'


def set_derived_sql(table: str, sql: str | None) -> None:
    if sql:
        st.session_state.derived_by_table[table] = sql
    else:
        st.session_state.derived_by_table.pop(table, None)
    get_value_overview.clear()
    get_summarize_for.clear()


_init_state()


# ---------------------------------------------------------------------------
# Sidebar — seleção e carregamento de arquivos
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("⚡ Parquet Query")
    st.caption("Dados versionados em `data/`")
    st.markdown("---")

    parquet_files = [p for p in list_data_files(DATA_DIR) if p.suffix.lower() == ".parquet"]

    if not parquet_files:
        st.warning("Nenhum `.parquet` encontrado em `data/`.")
    else:
        st.subheader("Bases disponíveis")
        selected: list[Path] = []
        for pf in parquet_files:
            size = fmt_bytes(pf.stat().st_size)
            version = version_from_stem(pf.stem)
            version_label = "original" if version is None else f"v{version}"
            checked = st.checkbox(
                f"{pf.stem}  `{size}`  · {version_label}",
                key=f"chk_{pf.stem}",
            )
            if checked:
                selected.append(pf)

        if st.button("Carregar selecionados", type="primary", disabled=not selected):
            for pf in selected:
                register_view(pf.stem, pf)
                if pf.stem not in st.session_state.loaded_tables:
                    st.session_state.loaded_tables.append(pf.stem)
                set_derived_sql(pf.stem, None)
            get_schema.clear()
            get_summarize.clear()
            get_summarize_for.clear()
            count_rows.clear()
            get_value_overview.clear()
            st.success(f"{len(selected)} tabela(s) carregada(s).")

    st.markdown("---")
    loaded = st.session_state.loaded_tables
    if loaded:
        st.subheader("Tabela ativa")
        active = st.selectbox("Selecionar tabela", loaded, key="active_table")
        if active:
            base_sql = working_sql(active)
            current_base = base_name_from(active)
            st.caption(f"Base: `{current_base}` · {count_rows_sql(base_sql):,} linhas")
            if active in st.session_state.derived_by_table:
                st.caption("Colunas calculadas ativas")

            timeline = build_timeline(DATA_DIR, current_base)
            if timeline:
                with st.expander("Timeline de versões", expanded=False):
                    for item in timeline:
                        files = ", ".join(f"`{f.name}`" for f in item["files"]) or "—"
                        meta = item.get("meta") or {}
                        updated = meta.get("updated_at") or meta.get("created_at")
                        when = f" · {updated[:16].replace('T', ' ')}" if updated else ""
                        st.markdown(f"**{item['label']}** — {files}{when}")
    else:
        st.info("Carregue ao menos um arquivo.")
        active = None


# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------
if not active:
    st.title("⚡ Parquet Query")
    st.info("Selecione e carregue um arquivo `.parquet` em `data/` na barra lateral para começar.")
    st.stop()

current_base = base_name_from(active)

schema_df = get_schema(active)
work_sql = working_sql(active)
work_schema_df = con.execute(f"DESCRIBE ({work_sql})").df()
col_names = work_schema_df["column_name"].tolist()
col_types = dict(zip(work_schema_df["column_name"], work_schema_df["column_type"]))
has_derived = active in st.session_state.derived_by_table

tabs = st.tabs(["Explorar", "SQL", "Filtros", "Agrupar", "Colunas", "Exportar"])


# ===========================================================================
# ABA 1 — EXPLORAR
# ===========================================================================
with tabs[0]:
    st.header(f"Explorar — {active}")
    if has_derived:
        st.caption("Exibindo tabela com colunas calculadas da aba Colunas.")

    subtab_schema, subtab_stats, subtab_overview, subtab_preview = st.tabs(
        ["Schema", "Estatísticas", "Overview de valores", "Preview"]
    )

    with subtab_schema:
        st.dataframe(work_schema_df, use_container_width=True, hide_index=True)
        if has_derived:
            with st.expander("Schema original do parquet"):
                st.dataframe(schema_df, use_container_width=True, hide_index=True)

    with subtab_stats:
        st.caption("Estatísticas calculadas pelo DuckDB (`SUMMARIZE`). Pode demorar alguns segundos na primeira vez.")
        if st.button("Calcular estatísticas", key="btn_summarize"):
            with st.spinner("Calculando..."):
                st.dataframe(get_summarize_for(work_sql), use_container_width=True, hide_index=True)

    with subtab_overview:
        overview_col = st.selectbox("Coluna", col_names, key="overview_col")
        overview_sql = build_value_overview_sql(work_sql, overview_col)

        with st.expander("SQL gerado"):
            st.code(overview_sql, language="sql")

        if st.button("Calcular overview", type="primary", key="btn_value_overview"):
            try:
                with st.spinner("Calculando frequências..."):
                    df_overview = get_value_overview(work_sql, overview_col)
                    distinct_count = len(df_overview)
                    total_rows = int(df_overview["quantidade"].sum()) if not df_overview.empty else 0
                    st.success(
                        f"{distinct_count:,} valor(es) distinto(s) · {total_rows:,} linhas contabilizadas"
                    )
                    st.dataframe(
                        paginate(df_overview, key="overview_page", page_size=100),
                        use_container_width=True,
                        hide_index=True,
                    )
            except Exception as e:
                st.error(f"Erro ao calcular overview: {e}")

    with subtab_preview:
        preview_cols = st.multiselect(
            "Colunas a exibir (vazio = todas)",
            col_names,
            key="preview_cols",
        )
        cols_expr = ", ".join(f'"{c}"' for c in preview_cols) if preview_cols else "*"
        preview_sql = f"SELECT {cols_expr} FROM ({work_sql}) __base__"
        df_preview, total_preview = paginate_sql(preview_sql, key="preview_page")
        st.dataframe(df_preview, use_container_width=True, hide_index=True)


# ===========================================================================
# ABA 2 — SQL
# ===========================================================================
with tabs[1]:
    st.header("Editor SQL")

    with st.expander("Referência rápida — tabelas e exemplos"):
        st.markdown(f"**Tabela ativa:** `{active}`")
        if has_derived:
            st.markdown("**Base de trabalho:** tabela com colunas calculadas (aba Colunas)")
        st.markdown("**Todas as tabelas carregadas:** " + ", ".join(f"`{t}`" for t in loaded))
        st.markdown("**Colunas disponíveis:** " + ", ".join(f"`{c}`" for c in col_names))
        st.code(
            f"""-- Preview (inclui colunas calculadas)
SELECT * FROM ({work_sql}) __base__ LIMIT 100;

-- Filtrar
SELECT * FROM ({work_sql}) __base__ WHERE valor > 1000;

-- Agrupar
SELECT categoria, SUM(valor) AS total
FROM ({work_sql}) __base__
GROUP BY 1 ORDER BY 2 DESC;
""",
            language="sql",
        )

    sql_input = st.text_area(
        "Query DuckDB",
        value=st.session_state.get("sql_editor", f"SELECT * FROM ({work_sql}) __base__ LIMIT 100"),
        height=180,
        key="sql_editor",
        placeholder=f"SELECT * FROM ({work_sql}) __base__ LIMIT 100",
    )

    col_run, col_clear = st.columns([1, 5])
    run_btn = col_run.button("Executar", type="primary", key="btn_sql_run")

    if run_btn and sql_input.strip():
        try:
            with st.spinner("Executando..."):
                # Conta linhas para paginação apenas se for SELECT
                stripped = sql_input.strip().upper()
                if stripped.startswith("SELECT") or stripped.startswith("WITH"):
                    df_sql, total_sql = paginate_sql(sql_input, key="sql_page")
                    st.session_state.last_result_sql = sql_input
                    st.success(f"{total_sql:,} linhas no resultado.")
                    st.dataframe(df_sql, use_container_width=True, hide_index=True)
                else:
                    con.execute(sql_input)
                    st.success("Comando executado.")
        except Exception as e:
            st.error(f"Erro SQL: {e}")


# ===========================================================================
# ABA 3 — FILTROS
# ===========================================================================
with tabs[2]:
    st.header("Filtros")

    def _type_category(dtype: str) -> str:
        d = dtype.upper()
        if any(t in d for t in ("INT", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "BIGINT", "HUGEINT", "REAL")):
            return "numeric"
        if any(t in d for t in ("DATE", "TIMESTAMP", "TIME")):
            return "date"
        return "text"

    # --- Adicionar filtro ---
    with st.expander("Adicionar filtro", expanded=True):
        f_col = st.selectbox("Coluna", col_names, key="f_col")
        f_dtype = col_types.get(f_col, "VARCHAR")
        f_cat = _type_category(f_dtype)

        if f_cat == "numeric":
            try:
                mn, mx = con.execute(
                    f'SELECT MIN("{f_col}"), MAX("{f_col}") FROM ({work_sql}) __base__'
                ).fetchone()
                mn = float(mn or 0)
                mx = float(mx or 0)
            except Exception:
                mn, mx = 0.0, 1.0
            f_op = st.selectbox("Operador", ["between", "=", "!=", ">", ">=", "<", "<="], key="f_op_num")
            if f_op == "between":
                f_v1, f_v2 = st.slider("Intervalo", mn, mx, (mn, mx), key="f_slider")
                clause = f'"{f_col}" BETWEEN {f_v1} AND {f_v2}'
                label = f"{f_col} BETWEEN {f_v1} AND {f_v2}"
            else:
                f_val = st.number_input("Valor", value=mn, key="f_num_val")
                clause = f'"{f_col}" {f_op} {f_val}'
                label = f"{f_col} {f_op} {f_val}"

        elif f_cat == "date":
            try:
                mn_d, mx_d = con.execute(
                    f'SELECT MIN("{f_col}"::DATE), MAX("{f_col}"::DATE) FROM ({work_sql}) __base__'
                ).fetchone()
            except Exception:
                mn_d, mx_d = None, None
            import datetime
            d1 = st.date_input("De", value=mn_d or datetime.date(2000, 1, 1), key="f_date1")
            d2 = st.date_input("Até", value=mx_d or datetime.date.today(), key="f_date2")
            clause = f'"{f_col}"::DATE BETWEEN \'{d1}\' AND \'{d2}\''
            label = f"{f_col} entre {d1} e {d2}"

        else:  # text
            f_text_op = st.selectbox("Operador", ["IN (seleção)", "LIKE", "NOT LIKE", "IS NULL", "IS NOT NULL"], key="f_text_op")
            if f_text_op == "IN (seleção)":
                opts = get_distinct_values(work_sql, f_col)
                chosen = st.multiselect("Valores", opts, key="f_vals")
                if chosen:
                    vals_str = ", ".join(f"'{v}'" for v in chosen)
                    clause = f'"{f_col}" IN ({vals_str})'
                    label = f"{f_col} IN ({', '.join(str(v) for v in chosen[:3])}{'...' if len(chosen) > 3 else ''})"
                else:
                    clause = None
                    label = None
            elif f_text_op in ("IS NULL", "IS NOT NULL"):
                clause = f'"{f_col}" {f_text_op}'
                label = f"{f_col} {f_text_op}"
            else:
                f_like_val = st.text_input("Padrão (use % como curinga)", key="f_like_val")
                clause = f"\"{f_col}\" {f_text_op} '{f_like_val}'"
                label = f"{f_col} {f_text_op} '{f_like_val}'"

        if st.button("Adicionar filtro", key="btn_add_filter"):
            if clause:
                st.session_state.filters.append({"label": label, "clause": clause})
                st.rerun()

    # --- Filtros ativos ---
    if st.session_state.filters:
        st.subheader("Filtros ativos")
        to_remove = []
        for i, f in enumerate(st.session_state.filters):
            c1, c2 = st.columns([8, 1])
            c1.markdown(f"`{f['label']}`")
            if c2.button("✕", key=f"rm_{i}"):
                to_remove.append(i)
        for i in reversed(to_remove):
            st.session_state.filters.pop(i)
        if to_remove:
            st.rerun()

        where_clause = " AND ".join(f['clause'] for f in st.session_state.filters)
        filter_sql = f"SELECT * FROM ({work_sql}) __base__ WHERE {where_clause}"

        with st.expander("SQL gerado"):
            st.code(filter_sql, language="sql")

        if st.button("Aplicar filtros", type="primary", key="btn_apply_filters"):
            try:
                with st.spinner("Filtrando..."):
                    df_filt, total_filt = paginate_sql(filter_sql, key="filter_page")
                    st.session_state.last_result_sql = filter_sql
                    st.success(f"{total_filt:,} linhas após filtros.")
                    st.dataframe(df_filt, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Erro: {e}")

        if st.button("Limpar todos os filtros", key="btn_clear_filters"):
            st.session_state.filters = []
            st.rerun()
    else:
        st.info("Nenhum filtro ativo. Adicione um acima.")


# ===========================================================================
# ABA 4 — AGRUPAR
# ===========================================================================
with tabs[3]:
    st.header("Agrupar")

    group_cols = st.multiselect("Colunas de agrupamento", col_names, key="group_cols")

    st.markdown("**Agregações**")
    agg_rows: list[dict] = []

    num_aggs = st.number_input("Quantas agregações?", min_value=1, max_value=20, value=1, step=1, key="num_aggs")
    for i in range(int(num_aggs)):
        c1, c2, c3 = st.columns([3, 2, 3])
        agg_col = c1.selectbox("Coluna", col_names, key=f"agg_col_{i}")
        agg_fn = c2.selectbox("Função", AGGS, key=f"agg_fn_{i}")
        agg_alias = c3.text_input("Alias", value=f"{agg_fn.lower().replace(' ', '_')}_{agg_col}", key=f"agg_alias_{i}")
        agg_rows.append({"col": agg_col, "fn": agg_fn, "alias": agg_alias})

    order_col = st.selectbox("Ordenar por", ["(sem ordenação)"] + [r["alias"] for r in agg_rows], key="group_order")
    order_dir = st.radio("Direção", ["DESC", "ASC"], horizontal=True, key="group_dir")

    if st.button("Executar agrupamento", type="primary", key="btn_group"):
        if not group_cols:
            st.warning("Selecione ao menos uma coluna de agrupamento.")
        else:
            agg_exprs = []
            for r in agg_rows:
                fn = r["fn"]
                col = r["col"]
                alias = r["alias"]
                if fn == "COUNT DISTINCT":
                    expr = f'COUNT(DISTINCT "{col}") AS "{alias}"'
                else:
                    expr = f'{fn}("{col}") AS "{alias}"'
                agg_exprs.append(expr)

            group_expr = ", ".join(f'"{c}"' for c in group_cols)
            select_expr = group_expr + ", " + ", ".join(agg_exprs)
            group_sql = f"SELECT {select_expr} FROM ({work_sql}) __base__ GROUP BY {group_expr}"
            if order_col != "(sem ordenação)":
                group_sql += f' ORDER BY "{order_col}" {order_dir}'

            with st.expander("SQL gerado"):
                st.code(group_sql, language="sql")

            try:
                with st.spinner("Agrupando..."):
                    df_group, total_group = paginate_sql(group_sql, key="group_page")
                    st.session_state.last_result_sql = group_sql
                    st.success(f"{total_group:,} grupos.")
                    st.dataframe(df_group, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Erro: {e}")


# ===========================================================================
# ABA 5 — COLUNAS
# ===========================================================================
with tabs[4]:
    st.header("Transformar Colunas")

    base_sql = work_sql
    derived_cols = col_names

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
                placeholder=f'"{derived_cols[0]}" * 2',
                key="new_col_expr",
            )
            if st.button("Adicionar", key="btn_add_col"):
                if new_col_name and new_col_expr:
                    new_sql = f'SELECT *, ({new_col_expr}) AS "{new_col_name}" FROM ({base_sql}) __t__'
                    try:
                        con.execute(f"SELECT * FROM ({new_sql}) __t__ LIMIT 1")
                        set_derived_sql(active, new_sql)
                        st.success(f"Coluna `{new_col_name}` adicionada.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Expressão inválida: {e}")
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
                    "são mapeadas para as colunas da view atual. Suporta IF, FORMAT, TODAY, "
                    "`.[Date]`, `.[Year]`, etc."
                )

            pq_formula = st.text_area(
                "Fórmula Power BI (DAX)",
                height=140,
                key="pq_col_formula",
                placeholder="Minha Coluna = IF([valor] > 100, \"Alto\", \"Baixo\")",
            )

            if pq_formula.strip():
                try:
                    col_name, duck_expr = translate_power_column(normalize_power_formula(pq_formula))
                    st.caption(f"Traduzido para DuckDB — coluna `{col_name}`:")
                    st.code(duck_expr, language="sql")
                except ParseError as e:
                    st.warning(f"Fórmula inválida: {e}")
                except Exception as e:
                    st.warning(f"Não foi possível traduzir: {e}")

            if st.button("Adicionar fórmula", key="btn_add_pq_col"):
                if not pq_formula.strip():
                    st.warning("Cole uma fórmula no formato: Nome da Coluna = expressão")
                else:
                    try:
                        col_name, duck_expr = translate_power_column(normalize_power_formula(pq_formula))
                        new_sql = f'SELECT *, ({duck_expr}) AS "{col_name}" FROM ({base_sql}) __t__'
                        con.execute(f"SELECT * FROM ({new_sql}) __t__ LIMIT 1")
                        set_derived_sql(active, new_sql)
                        st.success(f"Coluna `{col_name}` adicionada via fórmula Power BI.")
                        st.rerun()
                    except ParseError as e:
                        st.error(f"Fórmula inválida: {e}")
                    except Exception as e:
                        st.error(f"Erro ao aplicar coluna: {e}")

    elif op == "Renomear coluna":
        rename_src = st.selectbox("Coluna original", derived_cols, key="rename_src")
        rename_dst = st.text_input("Novo nome", key="rename_dst")
        if st.button("Renomear", key="btn_rename"):
            if rename_dst:
                col_list = ", ".join(
                    f'"{c}" AS "{rename_dst}"' if c == rename_src else f'"{c}"'
                    for c in derived_cols
                )
                new_sql = f"SELECT {col_list} FROM ({base_sql}) __t__"
                set_derived_sql(active, new_sql)
                st.success(f"`{rename_src}` renomeada para `{rename_dst}`.")
                st.rerun()

    elif op == "Remover colunas":
        drop_cols = st.multiselect("Colunas a remover", derived_cols, key="drop_cols")
        if st.button("Remover", key="btn_drop"):
            if drop_cols:
                keep = [c for c in derived_cols if c not in drop_cols]
                col_list = ", ".join(f'"{c}"' for c in keep)
                new_sql = f"SELECT {col_list} FROM ({base_sql}) __t__"
                set_derived_sql(active, new_sql)
                st.success(f"{len(drop_cols)} coluna(s) removida(s).")
                st.rerun()

    elif op == "Cast de tipo":
        cast_col = st.selectbox("Coluna", derived_cols, key="cast_col")
        cast_type = st.selectbox("Tipo destino", CAST_TYPES, key="cast_type")
        if st.button("Aplicar cast", key="btn_cast"):
            col_list = ", ".join(
                f'TRY_CAST("{c}" AS {cast_type}) AS "{c}"' if c == cast_col else f'"{c}"'
                for c in derived_cols
            )
            new_sql = f"SELECT {col_list} FROM ({base_sql}) __t__"
            try:
                con.execute(f"SELECT * FROM ({new_sql}) __t__ LIMIT 1")
                set_derived_sql(active, new_sql)
                st.success(f"`{cast_col}` convertida para `{cast_type}`.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro no cast: {e}")

    st.markdown("---")

    current_sql = st.session_state.derived_by_table.get(active)
    if current_sql:
        with st.expander("SQL da view derivada atual"):
            st.code(current_sql, language="sql")

        c1, c2 = st.columns(2)
        if c1.button("Pré-visualizar resultado", key="btn_preview_derived"):
            try:
                df_der, total_der = paginate_sql(current_sql, key="derived_page")
                st.session_state.last_result_sql = current_sql
                st.success(f"{total_der:,} linhas.")
                st.dataframe(df_der, use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(f"Erro: {e}")

        if c2.button("Resetar transformações", key="btn_reset_derived"):
            set_derived_sql(active, None)
            st.rerun()
    else:
        st.info("Nenhuma transformação aplicada. Use as opções acima.")


# ===========================================================================
# ABA 6 — EXPORTAR
# ===========================================================================
with tabs[5]:
    st.header("Exportar")
    st.caption(f"Base de dados: `{current_base}` · destino padrão: `data/`")

    export_source = st.radio(
        "O que exportar?",
        [
            "Tabela com colunas calculadas",
            "Último resultado (SQL/Filtros/Agrupamento)",
            "Somente parquet original",
        ],
        key="export_source",
    )

    if export_source == "Tabela com colunas calculadas":
        export_sql = work_sql
    elif export_source == "Último resultado (SQL/Filtros/Agrupamento)":
        if st.session_state.last_result_sql:
            export_sql = st.session_state.last_result_sql
        else:
            st.warning("Nenhum resultado encontrado. Execute uma query, filtro ou agrupamento primeiro.")
            st.stop()
    else:
        export_sql = f'SELECT * FROM "{active}"'

    with st.expander("SQL que será exportado"):
        st.code(export_sql, language="sql")

    timeline = build_timeline(DATA_DIR, current_base)
    existing_versions = list_version_numbers(DATA_DIR, current_base)
    next_version = next_available_version(DATA_DIR, current_base)

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
                        "Atualizado": (meta.get("updated_at") or meta.get("created_at") or "—")[:16].replace("T", " "),
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
            suggested_stem = versioned_stem(current_base, export_version)
            st.caption(f"Próxima versão disponível: **v{export_version}**")
        else:
            if not existing_versions:
                st.warning("Não há versões `_vN` para sobrescrever.")
                export_version = next_version
                suggested_stem = versioned_stem(current_base, export_version)
            else:
                export_version = st.selectbox(
                    "Versão existente",
                    existing_versions,
                    format_func=lambda v: f"v{v}",
                    key="export_overwrite_version",
                )
                suggested_stem = versioned_stem(current_base, export_version)
                existing_files = files_for_version(DATA_DIR, current_base, export_version)
                if existing_files:
                    st.warning(
                        "Sobrescrever substitui: "
                        + ", ".join(f"`{f.name}`" for f in existing_files)
                    )

        defaults_key = f"{current_base}:{version_mode}:{export_version}:{export_fmt}"
        if st.session_state.get("export_defaults_key") != defaults_key:
            st.session_state.export_filename = suggested_stem
            st.session_state.export_defaults_key = defaults_key

        export_filename = st.text_input(
            "Nome do arquivo (sem extensão)",
            key="export_filename",
        )

        manifest = load_manifest(DATA_DIR)
        version_meta = manifest.get("bases", {}).get(current_base, {}).get("versions", {}).get(str(export_version))
        if version_meta:
            with st.expander("Configuração da versão selecionada"):
                st.json(version_meta)

    overwrite = version_mode == "Sobrescrever versão" and bool(existing_versions)
    dest_path = DATA_DIR / f"{export_filename}.{export_extension(export_fmt)}"
    st.caption(f"Destino: `{dest_path}`")

    col_dl, col_save = st.columns(2)

    if col_dl.button("Baixar arquivo", type="primary", key="btn_download"):
        try:
            with st.spinner("Preparando arquivo..."):
                df_exp = run_query(export_sql)

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
        except Exception as e:
            st.error(f"Erro ao exportar: {e}")

    if col_save.button("Salvar em data/", key="btn_save_data"):
        try:
            with st.spinner("Salvando..."):
                df_exp = run_query(export_sql)

                if export_fmt == "XLSX" and len(df_exp) > LIMITE_XLSX:
                    df_exp = df_exp.head(LIMITE_XLSX)
                    st.warning(f"Exportado com limite de {LIMITE_XLSX:,} linhas.")

                if overwrite:
                    for old_file in files_for_version(DATA_DIR, current_base, export_version):
                        if old_file != dest_path:
                            old_file.unlink()

                dest = save_to_data(df_exp, dest_path, export_fmt, overwrite=overwrite)
                record_version(
                    DATA_DIR,
                    current_base,
                    export_version,
                    filename=dest.name,
                    fmt=export_fmt,
                    source_table=active,
                    export_source=export_source,
                    overwrite=overwrite,
                )
                st.success(f"Versão salva em `{dest}`")
                if dest.suffix.lower() == ".parquet" and dest.stem not in st.session_state.loaded_tables:
                    st.caption("Recarregue o arquivo na barra lateral para trabalhar com esta versão.")
                st.rerun()
        except FileExistsError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

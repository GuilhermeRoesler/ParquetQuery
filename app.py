#!/usr/bin/env python3
"""Streamlit Parquet Query — exploração de parquets com DuckDB."""

from __future__ import annotations

import io
from pathlib import Path
from typing import NamedTuple

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


LOADABLE_EXTENSIONS = {".parquet", ".csv"}


def duckdb_read_expr(path: Path) -> str:
    ext = path.suffix.lower()
    posix = path.as_posix().replace("'", "''")
    if ext == ".parquet":
        return f"read_parquet('{posix}')"
    if ext == ".csv":
        return f"read_csv_auto('{posix}')"
    raise ValueError(f"Formato não suportado para leitura: {ext}")


def register_view(name: str, path: Path) -> None:
    source = duckdb_read_expr(path)
    con.execute(f'CREATE OR REPLACE VIEW "{name}" AS SELECT * FROM {source}')


def list_views() -> list[str]:
    return [r[0] for r in con.execute("SHOW TABLES").fetchall()]


@st.cache_data(ttl=300)
def get_schema(table: str) -> pd.DataFrame:
    return con.execute(f'DESCRIBE "{table}"').df()


@st.cache_data(ttl=300)
def count_rows(table: str) -> int:
    return con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]


OVERVIEW_AGGS = ["MIN", "MAX", "SUM", "AVG"]


def column_type_category(dtype: str) -> str:
    d = dtype.upper()
    if any(t in d for t in ("INT", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "BIGINT", "HUGEINT", "REAL")):
        return "numeric"
    if any(t in d for t in ("DATE", "TIMESTAMP", "TIME")):
        return "date"
    return "text"


def _numeric_overview_expr(col: str, dtype: str) -> str:
    if column_type_category(dtype) == "text":
        return f'TRY_CAST(TRIM("{col}") AS DOUBLE)'
    return f'"{col}"'


def _format_int_pt(n: int) -> str:
    s = str(abs(n))
    parts: list[str] = []
    while s:
        parts.append(s[-3:])
        s = s[:-3]
    formatted = ".".join(reversed(parts))
    return f"-{formatted}" if n < 0 else formatted


def format_number_pt(value, *, max_decimals: int = 6) -> str:
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except TypeError:
        pass
    if hasattr(value, "strftime"):
        if hasattr(value, "hour") and (value.hour or value.minute or value.second):
            return value.strftime("%d/%m/%Y %H:%M:%S")
        return value.strftime("%d/%m/%Y")

    num = float(value)
    if num == int(num) and abs(num) < 1e18:
        return _format_int_pt(int(num))

    sign = "-" if num < 0 else ""
    num = abs(num)
    raw = f"{num:.{max_decimals}f}".rstrip("0").rstrip(".")
    int_s, _, dec_s = raw.partition(".")
    int_formatted = _format_int_pt(int(int_s or "0"))
    if dec_s:
        return f"{sign}{int_formatted},{dec_s}"
    return f"{sign}{int_formatted}"


def build_classificatory_overview_sql(table: str, col: str) -> str:
    wf = work_from(table)
    return (
        f'SELECT "{col}", COUNT(*) AS "quantidade"\n'
        f"FROM {wf}\n"
        f'GROUP BY "{col}"\n'
        f'ORDER BY "quantidade" DESC'
    )


def build_numeric_overview_sql(table: str, col: str, agg: str, dtype: str) -> str:
    expr = _numeric_overview_expr(col, dtype)
    return f'SELECT {agg}({expr}) AS "resultado"\nFROM {work_from(table)}'


@st.cache_data(ttl=300)
def get_classificatory_overview(table: str, col: str) -> pd.DataFrame:
    return con.execute(build_classificatory_overview_sql(table, col)).df()


@st.cache_data(ttl=300)
def get_numeric_overview(table: str, col: str, agg: str, dtype: str):
    return con.execute(build_numeric_overview_sql(table, col, agg, dtype)).fetchone()[0]


def count_work_rows(table: str) -> int:
    return con.execute(f"SELECT COUNT(*) FROM {work_from(table)}").fetchone()[0]


def run_query(sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


class PageInfo(NamedTuple):
    page: int
    pages: int
    total: int
    page_size: int


def _pagination_page(key: str, pages: int) -> int:
    state_key = f"pg_{key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = 1
    page = int(st.session_state[state_key])
    page = max(1, min(page, pages))
    st.session_state[state_key] = page
    return page


def render_pagination_bar(key: str, info: PageInfo) -> None:
    if info.pages <= 1:
        if info.total > 0:
            with st.container(horizontal=True, horizontal_alignment="center"):
                st.caption(f"{info.total:,} linha(s)")
        return

    pk = f"pg_{key}"
    start = (info.page - 1) * info.page_size + 1
    end = min(info.page * info.page_size, info.total)

    with st.container(
        horizontal=True,
        horizontal_alignment="center",
        vertical_alignment="center",
        gap="small",
    ):
        if st.button("◀", key=f"{pk}_prev", disabled=info.page <= 1):
            st.session_state[pk] = info.page - 1
            st.rerun()
        st.markdown(
            f"<span style='font-size:0.875rem;white-space:nowrap'>{start:,}–{end:,} de {info.total:,} · "
            f"<strong>{info.page}/{info.pages}</strong></span>",
            unsafe_allow_html=True,
        )
        if st.button("▶", key=f"{pk}_next", disabled=info.page >= info.pages):
            st.session_state[pk] = info.page + 1
            st.rerun()


def show_paginated_dataframe(df: pd.DataFrame, info: PageInfo, key: str) -> None:
    st.dataframe(df, use_container_width=True, hide_index=True)
    render_pagination_bar(key, info)


def paginate(df: pd.DataFrame, key: str, page_size: int = 500) -> tuple[pd.DataFrame, PageInfo]:
    total = len(df)
    pages = max(1, (total + page_size - 1) // page_size)
    page = _pagination_page(key, pages)
    offset = (page - 1) * page_size
    info = PageInfo(page, pages, total, page_size)
    return df.iloc[offset : offset + page_size], info


def paginate_sql(sql: str, key: str, page_size: int = 500) -> tuple[pd.DataFrame, PageInfo]:
    """Paginação diretamente no DuckDB — não carrega tudo na RAM."""
    sql = strip_sql(sql)
    total = con.execute(f"SELECT COUNT(*) FROM ({sql}) __q__").fetchone()[0]
    pages = max(1, (total + page_size - 1) // page_size)
    page = _pagination_page(key, pages)
    offset = (page - 1) * page_size
    df = con.execute(f"SELECT * FROM ({sql}) __q__ LIMIT {page_size} OFFSET {offset}").df()
    return df, PageInfo(page, pages, total, page_size)


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
        "derived_by_table": {},
        "last_result_sql": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    st.session_state.pop("derived_select", None)
    st.session_state.pop("working_sql_cache", None)


def strip_sql(sql: str) -> str:
    """Remove espaços e ponto-e-vírgula final."""
    return sql.strip().rstrip(";")


def get_derived_sql(table: str) -> str | None:
    return st.session_state.derived_by_table.get(table)


def has_derived_sql(table: str) -> bool:
    return table in st.session_state.derived_by_table


def work_from(table: str) -> str:
    """Fragmento para cláusula FROM: tabela DuckDB ou subquery derivada."""
    derived = get_derived_sql(table)
    if derived:
        return f"({derived}) __work__"
    return f'"{table}"'


def default_preview_sql(table: str, *, limit: int = 100) -> str:
    return f"SELECT * FROM {work_from(table)} LIMIT {limit}"


def build_derived_select(table: str, select_expr: str) -> str:
    return f"SELECT {select_expr} FROM {work_from(table)}"


def working_sql(table: str) -> str:
    """SQL completo da base de trabalho (para export/DESCRIBE)."""
    derived = get_derived_sql(table)
    if derived:
        return derived
    return f'SELECT * FROM "{table}"'


def set_derived_sql(table: str, sql: str | None) -> None:
    if sql:
        st.session_state.derived_by_table[table] = sql
    else:
        st.session_state.derived_by_table.pop(table, None)
    get_classificatory_overview.clear()
    get_numeric_overview.clear()
    st.session_state.pop("sql_editor_ctx", None)


_init_state()


# ---------------------------------------------------------------------------
# Sidebar — seleção e carregamento de arquivos
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("⚡ Parquet Query")
    st.caption("Dados versionados em `data/`")
    st.markdown("---")

    data_files = [p for p in list_data_files(DATA_DIR) if p.suffix.lower() in LOADABLE_EXTENSIONS]

    if not data_files:
        st.warning("Nenhum `.parquet` ou `.csv` encontrado em `data/`.")
    else:
        st.subheader("Bases disponíveis")
        selected: list[Path] = []
        for df_path in data_files:
            size = fmt_bytes(df_path.stat().st_size)
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
                register_view(df_path.stem, df_path)
                if df_path.stem not in st.session_state.loaded_tables:
                    st.session_state.loaded_tables.append(df_path.stem)
                set_derived_sql(df_path.stem, None)
            get_schema.clear()
            count_rows.clear()
            get_classificatory_overview.clear()
            get_numeric_overview.clear()
            st.success(f"{len(selected)} tabela(s) carregada(s).")

    st.markdown("---")
    loaded = st.session_state.loaded_tables
    if loaded:
        st.subheader("Tabela ativa")
        active = st.selectbox("Selecionar tabela", loaded, key="active_table")
        if active:
            current_base = base_name_from(active)
            st.caption(f"Base: `{current_base}` · {count_work_rows(active):,} linhas")
            if has_derived_sql(active):
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
    st.info("Selecione e carregue um arquivo `.parquet` ou `.csv` em `data/` na barra lateral para começar.")
    st.stop()

current_base = base_name_from(active)

schema_df = get_schema(active)
work_from_clause = work_from(active)
work_sql = working_sql(active)
if has_derived_sql(active):
    work_schema_df = con.execute(f"DESCRIBE ({get_derived_sql(active)})").df()
else:
    work_schema_df = schema_df
col_names = work_schema_df["column_name"].tolist()
col_types = dict(zip(work_schema_df["column_name"], work_schema_df["column_type"]))
has_derived = has_derived_sql(active)

sql_editor_ctx = f"{active}:{'derived' if has_derived else 'raw'}"
if st.session_state.get("sql_editor_ctx") != sql_editor_ctx:
    st.session_state.sql_editor = default_preview_sql(active)
    st.session_state.sql_editor_ctx = sql_editor_ctx

tabs = st.tabs(["Explorar", "SQL", "Colunas", "Exportar"])


# ===========================================================================
# ABA 1 — EXPLORAR
# ===========================================================================
with tabs[0]:
    st.header(f"Explorar — {active}")
    if has_derived:
        st.caption("Exibindo tabela com colunas calculadas da aba Colunas.")

    subtab_schema, subtab_preview, subtab_overview = st.tabs(
        ["Schema", "Preview", "Overview de valores"]
    )

    with subtab_schema:
        st.dataframe(work_schema_df, use_container_width=True, hide_index=True)
        if has_derived:
            with st.expander("Schema original do arquivo"):
                st.dataframe(schema_df, use_container_width=True, hide_index=True)

    with subtab_preview:
        preview_cols = st.multiselect(
            "Colunas a exibir (vazio = todas)",
            col_names,
            key="preview_cols",
        )
        cols_expr = ", ".join(f'"{c}"' for c in preview_cols) if preview_cols else "*"
        preview_sql = f"SELECT {cols_expr} FROM {work_from_clause}"
        df_preview, preview_info = paginate_sql(preview_sql, key="preview_page")
        show_paginated_dataframe(df_preview, preview_info, "preview_page")

    with subtab_overview:
        overview_mode = st.radio(
            "Tipo de overview",
            ["Classificatório", "Numérico"],
            horizontal=True,
            key="overview_mode",
        )
        overview_col = st.selectbox("Coluna", col_names, key="overview_col")
        overview_dtype = col_types.get(overview_col, "VARCHAR")

        if overview_mode == "Numérico":
            overview_agg = st.selectbox("Agregação", OVERVIEW_AGGS, key="overview_agg")
            overview_sql = build_numeric_overview_sql(active, overview_col, overview_agg, overview_dtype)
        else:
            overview_agg = None
            overview_sql = build_classificatory_overview_sql(active, overview_col)

        with st.expander("SQL gerado"):
            st.code(overview_sql, language="sql")

        if st.button("Calcular overview", type="primary", key="btn_value_overview"):
            try:
                if overview_mode == "Classificatório":
                    with st.spinner("Calculando frequências..."):
                        df_overview = get_classificatory_overview(active, overview_col)
                        distinct_count = len(df_overview)
                        total_rows = int(df_overview["quantidade"].sum()) if not df_overview.empty else 0
                        st.success(
                            f"{distinct_count:,} valor(es) distinto(s) · {total_rows:,} linhas contabilizadas"
                        )
                        df_overview_page, overview_info = paginate(
                            df_overview, key="overview_page", page_size=100
                        )
                        show_paginated_dataframe(df_overview_page, overview_info, "overview_page")
                else:
                    with st.spinner("Calculando agregação..."):
                        result = get_numeric_overview(active, overview_col, overview_agg, overview_dtype)
                        formatted = format_number_pt(result)
                        st.markdown(
                            f"<p style='font-size:2.25rem;font-weight:600;margin:0.5rem 0'>"
                            f"{formatted}</p>",
                            unsafe_allow_html=True,
                        )
                        st.caption(f"{overview_agg} · `{overview_col}`")
            except Exception as e:
                st.error(f"Erro ao calcular overview: {e}")


# ===========================================================================
# ABA 2 — SQL
# ===========================================================================
with tabs[1]:
    st.header("Editor SQL")

    with st.expander("Referência rápida — tabelas e exemplos"):
        st.markdown(f"**Tabela ativa:** `{active}`")
        if has_derived:
            st.markdown("**Base de trabalho:** inclui colunas calculadas (aba Colunas)")
            st.caption(
                f"Para ver todas as colunas, use `FROM {work_from_clause}` — "
                f"consultar só `\"{active}\"` retorna apenas o arquivo original."
            )
        st.markdown("**Todas as tabelas carregadas:** " + ", ".join(f"`{t}`" for t in loaded))
        st.markdown("**Colunas disponíveis:** " + ", ".join(f"`{c}`" for c in col_names))
        frm = work_from_clause
        derived_note = (
            "\n-- Com colunas calculadas: use a subquery __work__ (gerada automaticamente)\n"
            if has_derived
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

    default_sql = default_preview_sql(active)
    sql_input = st.text_area(
        "Query DuckDB",
        height=180,
        key="sql_editor",
        placeholder=default_sql,
    )

    col_run, col_clear = st.columns([1, 5])
    run_btn = col_run.button("Executar", type="primary", key="btn_sql_run")

    if run_btn and sql_input.strip():
        try:
            with st.spinner("Executando..."):
                query = strip_sql(sql_input)
                stripped = query.upper()
                if stripped.startswith("SELECT") or stripped.startswith("WITH"):
                    df_sql, sql_info = paginate_sql(query, key="sql_page")
                    st.session_state.last_result_sql = query
                    st.success(f"{sql_info.total:,} linhas no resultado.")
                    show_paginated_dataframe(df_sql, sql_info, "sql_page")
                else:
                    con.execute(query)
                    st.success("Comando executado.")
        except Exception as e:
            st.error(f"Erro SQL: {e}")


# ===========================================================================
# ABA 3 — COLUNAS
# ===========================================================================
with tabs[2]:
    st.header("Transformar Colunas")

    base_table = active
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
                    new_sql = build_derived_select(
                        base_table, f'*, ({new_col_expr}) AS "{new_col_name}"'
                    )
                    try:
                        con.execute(f"SELECT * FROM ({new_sql}) __validate__ LIMIT 1")
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
                    "são mapeadas para as colunas da view atual. Suporta IF, VAR/RETURN, comentários `--`, "
                    "SUBSTITUTE, FIND, SEARCH, TRIM, LEFT, FORMAT, TODAY, `.[Date]`, etc."
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
                        new_sql = build_derived_select(
                            base_table, f'*, ({duck_expr}) AS "{col_name}"'
                        )
                        con.execute(f"SELECT * FROM ({new_sql}) __validate__ LIMIT 1")
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
                new_sql = build_derived_select(base_table, col_list)
                set_derived_sql(active, new_sql)
                st.success(f"`{rename_src}` renomeada para `{rename_dst}`.")
                st.rerun()

    elif op == "Remover colunas":
        drop_cols = st.multiselect("Colunas a remover", derived_cols, key="drop_cols")
        if st.button("Remover", key="btn_drop"):
            if drop_cols:
                keep = [c for c in derived_cols if c not in drop_cols]
                col_list = ", ".join(f'"{c}"' for c in keep)
                new_sql = build_derived_select(base_table, col_list)
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
            new_sql = build_derived_select(base_table, col_list)
            try:
                con.execute(f"SELECT * FROM ({new_sql}) __validate__ LIMIT 1")
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
                df_der, der_info = paginate_sql(current_sql, key="derived_page")
                st.session_state.last_result_sql = current_sql
                st.success(f"{der_info.total:,} linhas.")
                show_paginated_dataframe(df_der, der_info, "derived_page")
            except Exception as e:
                st.error(f"Erro: {e}")

        if c2.button("Resetar transformações", key="btn_reset_derived"):
            set_derived_sql(active, None)
            st.rerun()
    else:
        st.info("Nenhuma transformação aplicada. Use as opções acima.")


# ===========================================================================
# ABA 4 — EXPORTAR
# ===========================================================================
with tabs[3]:
    st.header("Exportar")
    st.caption(f"Base de dados: `{current_base}` · destino padrão: `data/`")

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
        export_sql = work_sql
    elif export_source == "Último resultado (SQL)":
        if st.session_state.last_result_sql:
            export_sql = st.session_state.last_result_sql
        else:
            st.warning("Nenhum resultado encontrado. Execute uma query na aba SQL primeiro.")
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
                if dest.suffix.lower() in LOADABLE_EXTENSIONS and dest.stem not in st.session_state.loaded_tables:
                    st.caption("Recarregue o arquivo na barra lateral para trabalhar com esta versão.")
                st.rerun()
        except FileExistsError as e:
            st.error(str(e))
        except Exception as e:
            st.error(f"Erro ao salvar: {e}")

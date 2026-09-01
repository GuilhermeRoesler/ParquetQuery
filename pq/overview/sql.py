"""Geração de SQL para overview de valores."""

from __future__ import annotations

from pq.db.derived import work_from_clause
from pq.db.sql_utils import quote_ident


def column_type_category(dtype: str) -> str:
    d = dtype.upper()
    if any(t in d for t in ("INT", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "BIGINT", "HUGEINT", "REAL")):
        return "numeric"
    if any(t in d for t in ("DATE", "TIMESTAMP", "TIME")):
        return "date"
    return "text"


def _numeric_overview_expr(col: str, dtype: str) -> str:
    qcol = quote_ident(col)
    if column_type_category(dtype) == "text":
        return f"TRY_CAST(TRIM({qcol}) AS DOUBLE)"
    return qcol


def build_classificatory_overview_sql(
    table: str,
    col: str,
    derived_sql: str | None,
) -> str:
    qcol = quote_ident(col)
    wf = work_from_clause(table, derived_sql)
    return (
        f"SELECT {qcol}, COUNT(*) AS {quote_ident('quantidade')}\n"
        f"FROM {wf}\n"
        f"GROUP BY {qcol}\n"
        f'ORDER BY {quote_ident("quantidade")} DESC'
    )


def build_classificatory_overview_summary_sql(
    table: str,
    col: str,
    derived_sql: str | None,
) -> str:
    overview = build_classificatory_overview_sql(table, col, derived_sql)
    return (
        f"SELECT COUNT(*) AS {quote_ident('distinct_count')}, "
        f"COALESCE(SUM({quote_ident('quantidade')}), 0) AS {quote_ident('total_rows')}\n"
        f"FROM ({overview}) __ov__"
    )


def build_numeric_overview_sql(
    table: str,
    col: str,
    agg: str,
    dtype: str,
    derived_sql: str | None,
) -> str:
    expr = _numeric_overview_expr(col, dtype)
    wf = work_from_clause(table, derived_sql)
    return f"SELECT {agg}({expr}) AS {quote_ident('resultado')}\nFROM {wf}"

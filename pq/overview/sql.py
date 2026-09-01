"""Geração de SQL para overview de valores."""

from __future__ import annotations

from pq.db.derived import work_from_clause


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


def build_classificatory_overview_sql(
    table: str,
    col: str,
    derived_sql: str | None,
) -> str:
    wf = work_from_clause(table, derived_sql)
    return (
        f'SELECT "{col}", COUNT(*) AS "quantidade"\n'
        f"FROM {wf}\n"
        f'GROUP BY "{col}"\n'
        f'ORDER BY "quantidade" DESC'
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
    return f'SELECT {agg}({expr}) AS "resultado"\nFROM {wf}'

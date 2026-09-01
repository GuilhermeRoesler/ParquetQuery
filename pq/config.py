"""Constantes e caminhos do projeto."""

from __future__ import annotations

import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DATA_DIR = BASE / "data"
DEMO_DIR = BASE / "demo"
CLOUD_UPLOAD_MAX_BYTES = 50 * 1024 * 1024


def is_cloud_mode() -> bool:
    """True no Streamlit Community Cloud ou com PQ_CLOUD_MODE=1 (teste local)."""
    override = os.environ.get("PQ_CLOUD_MODE", "").lower()
    if override in ("1", "true", "yes"):
        return True
    if override in ("0", "false", "no"):
        return False

    if os.environ.get("STREAMLIT_RUNTIME_ENVIRONMENT") == "cloud":
        return True
    if os.environ.get("STREAMLIT_SHARING") or os.environ.get("STREAMLIT_CLOUD"):
        return True

    # Community Cloud monta o repositório em /mount/src/<repo>/ (Linux).
    try:
        if BASE.resolve().as_posix().startswith("/mount/src/"):
            return True
    except OSError:
        pass

    return False


LOADABLE_EXTENSIONS = {".parquet", ".csv"}
CAST_TYPES = ["VARCHAR", "INTEGER", "BIGINT", "DOUBLE", "BOOLEAN", "DATE", "TIMESTAMP"]
LIMITE_XLSX = 1_048_576
OVERVIEW_AGGS = ["MIN", "MAX", "SUM", "AVG"]

SQL_KEYWORDS = [
    "SELECT",
    "FROM",
    "WHERE",
    "GROUP BY",
    "ORDER BY",
    "HAVING",
    "LIMIT",
    "OFFSET",
    "AS",
    "AND",
    "OR",
    "NOT",
    "IN",
    "IS",
    "NULL",
    "LIKE",
    "ILIKE",
    "BETWEEN",
    "DISTINCT",
    "JOIN",
    "INNER JOIN",
    "LEFT JOIN",
    "RIGHT JOIN",
    "FULL JOIN",
    "CROSS JOIN",
    "ON",
    "UNION",
    "UNION ALL",
    "WITH",
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
    "ASC",
    "DESC",
    "EXISTS",
    "CAST",
    "TRY_CAST",
]

DUCKDB_FUNCTIONS = [
    "COUNT",
    "SUM",
    "AVG",
    "MIN",
    "MAX",
    "MEDIAN",
    "STDDEV",
    "VARIANCE",
    "STRING_AGG",
    "LIST",
    "ARRAY_AGG",
    "FIRST",
    "LAST",
    "QUANTILE",
    "UPPER",
    "LOWER",
    "TRIM",
    "LTRIM",
    "RTRIM",
    "LENGTH",
    "SUBSTRING",
    "REPLACE",
    "CONCAT",
    "COALESCE",
    "NULLIF",
    "IFNULL",
    "DATE_TRUNC",
    "EXTRACT",
    "YEAR",
    "MONTH",
    "DAY",
    "strftime",
    "strptime",
    "CURRENT_DATE",
    "CURRENT_TIMESTAMP",
    "TODAY",
    "ROUND",
    "FLOOR",
    "CEIL",
    "ABS",
    "SQRT",
    "POWER",
    "GREATEST",
    "LEAST",
    "ROW_NUMBER",
    "RANK",
    "DENSE_RANK",
    "LAG",
    "LEAD",
    "REGEXP_MATCHES",
    "SPLIT_PART",
    "LIST_VALUE",
    "UNNEST",
    "typeof",
    "read_parquet",
    "read_csv_auto",
]

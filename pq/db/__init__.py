"""Camada DuckDB — conexão, schema e queries."""

from pq.db.connection import duckdb_read_expr, get_connection, list_views, register_view, run_query
from pq.db.derived import (
    build_derived_select,
    default_preview_sql,
    work_from_clause,
    working_sql,
)
from pq.db.sql_utils import quote_ident, strip_sql, validate_derived_sql

__all__ = [
    "build_derived_select",
    "default_preview_sql",
    "duckdb_read_expr",
    "get_connection",
    "list_views",
    "quote_ident",
    "register_view",
    "run_query",
    "strip_sql",
    "validate_derived_sql",
    "work_from_clause",
    "working_sql",
]

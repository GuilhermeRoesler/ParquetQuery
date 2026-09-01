"""Utilitários SQL genéricos."""

from __future__ import annotations

import duckdb


def strip_sql(sql: str) -> str:
    """Remove espaços e ponto-e-vírgula final."""
    return sql.strip().rstrip(";")


def quote_ident(name: str) -> str:
    """Escapa identificador SQL com aspas duplas (DuckDB)."""
    return '"' + name.replace('"', '""') + '"'


def validate_derived_sql(con: duckdb.DuckDBPyConnection, sql: str) -> None:
    """Valida SQL derivado executando SELECT LIMIT 1."""
    query = strip_sql(sql)
    con.execute(f"SELECT * FROM ({query}) __validate__ LIMIT 1")

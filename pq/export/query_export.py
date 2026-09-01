"""Exportação de queries DuckDB sem carregar dataset inteiro na RAM."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import NamedTuple

import duckdb
from openpyxl import Workbook

from pq.config import LIMITE_XLSX
from pq.db.sql_utils import strip_sql
from pq.export.io import export_extension


class ExportResult(NamedTuple):
    row_count: int
    truncated: bool


def _duckdb_copy_path(con: duckdb.DuckDBPyConnection, sql: str, dest: Path, fmt: str) -> None:
    query = strip_sql(sql)
    posix = dest.as_posix().replace("'", "''")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "Parquet":
        con.execute(f"COPY ({query}) TO '{posix}' (FORMAT PARQUET)")
        return
    if fmt == "CSV":
        con.execute(
            f"COPY ({query}) TO '{posix}' (FORMAT CSV, HEADER, DELIMITER ',')"
        )
        return
    raise ValueError(f"Formato não suportado para COPY: {fmt}")


def _export_xlsx_chunked(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    dest: Path,
    *,
    limit: int = LIMITE_XLSX,
) -> ExportResult:
    query = strip_sql(sql)
    result = con.execute(query)
    dest.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook(write_only=True)
    ws = wb.create_sheet()
    rows_written = 0
    truncated = False
    header_done = False

    while rows_written < limit:
        chunk_size = min(10_000, limit - rows_written)
        chunk = result.fetch_df_chunk(chunk_size)
        if chunk is None or chunk.empty:
            break
        if rows_written + len(chunk) > limit:
            chunk = chunk.iloc[: limit - rows_written]
            truncated = True
        if not header_done:
            ws.append(list(chunk.columns))
            header_done = True
        for row in chunk.itertuples(index=False, name=None):
            ws.append(list(row))
            rows_written += 1
        if truncated:
            break

    wb.save(dest)
    return ExportResult(rows_written, truncated)


def export_query_to_path(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    dest: Path,
    fmt: str,
    *,
    xlsx_limit: int = LIMITE_XLSX,
) -> ExportResult:
    """Exporta query para disco via DuckDB COPY (Parquet/CSV) ou chunks (XLSX)."""
    if fmt == "XLSX":
        return _export_xlsx_chunked(con, sql, dest, limit=xlsx_limit)

    _duckdb_copy_path(con, sql, dest, fmt)
    query = strip_sql(sql)
    row_count = con.execute(f"SELECT COUNT(*) FROM ({query}) __q__").fetchone()[0]
    return ExportResult(int(row_count), False)


def export_query_to_bytes(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    fmt: str,
    *,
    xlsx_limit: int = LIMITE_XLSX,
) -> tuple[bytes, str, ExportResult]:
    """Exporta query para bytes usando arquivo temporário."""
    ext = export_extension(fmt)
    mime_map = {
        "csv": "text/csv",
        "parquet": "application/vnd.apache.parquet",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }

    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        export_result = export_query_to_path(
            con, sql, tmp_path, fmt, xlsx_limit=xlsx_limit
        )
        return tmp_path.read_bytes(), mime_map[ext], export_result
    finally:
        tmp_path.unlink(missing_ok=True)

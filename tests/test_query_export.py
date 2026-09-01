from __future__ import annotations

import duckdb

from pq.export.query_export import export_query_to_bytes, export_query_to_path


def test_export_parquet_via_copy(tmp_path) -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t AS SELECT 1 AS a, 'x' AS b UNION ALL SELECT 2, 'y'")
    sql = "SELECT * FROM t ORDER BY a"
    dest = tmp_path / "out.parquet"

    result = export_query_to_path(con, sql, dest, "Parquet")
    assert dest.exists()
    assert result.row_count == 2
    assert result.truncated is False


def test_export_csv_bytes(tmp_path) -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t AS SELECT 42 AS n")
    data, mime, result = export_query_to_bytes(con, "SELECT n FROM t", "CSV")
    assert mime == "text/csv"
    assert b"42" in data
    assert result.row_count == 1

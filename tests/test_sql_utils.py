from __future__ import annotations

import duckdb
import pytest

from pq.db.sql_utils import quote_ident, strip_sql, validate_derived_sql


def test_strip_sql() -> None:
    assert strip_sql("SELECT 1;  ") == "SELECT 1"


def test_quote_ident_simple() -> None:
    assert quote_ident("coluna") == '"coluna"'


def test_quote_ident_escapes_quotes() -> None:
    assert quote_ident('a"b') == '"a""b"'


def test_validate_derived_sql_ok() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t AS SELECT 1 AS x")
    validate_derived_sql(con, "SELECT * FROM t")


def test_validate_derived_sql_fail() -> None:
    con = duckdb.connect()
    with pytest.raises(duckdb.Error):
        validate_derived_sql(con, "SELECT nope FROM missing")

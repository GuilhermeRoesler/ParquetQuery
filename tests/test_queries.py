from __future__ import annotations

import duckdb

from pq.db.queries import count_from_sql, count_query


def test_count_from_sql() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t AS SELECT * FROM range(5)")
    assert count_from_sql(con, "t") == 5


def test_count_from_sql_subquery() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t AS SELECT * FROM range(3)")
    assert count_from_sql(con, '(SELECT "range" FROM t WHERE "range" > 0) __sub__') == 2


def test_count_query() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t AS SELECT * FROM range(4)")
    assert count_query(con, "SELECT * FROM t WHERE range >= 2") == 2

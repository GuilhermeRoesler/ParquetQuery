from __future__ import annotations

import duckdb

from pq.db.schema import describe_sql, table_column_names


def test_describe_sql() -> None:
    con = duckdb.connect()
    con.execute("CREATE TABLE t AS SELECT 1 AS x, 'a' AS y")
    df = describe_sql(con, "SELECT * FROM t")
    assert set(df["column_name"]) == {"x", "y"}


def test_table_column_names_raw_table(monkeypatch) -> None:
    con = duckdb.connect()
    con.execute('CREATE TABLE "minha_tabela" AS SELECT 10 AS id, 20 AS valor')

    def fake_get_schema(table: str):
        return con.execute(f'DESCRIBE "{table}"').df()

    monkeypatch.setattr("pq.db.schema.get_schema", fake_get_schema)
    cols = table_column_names(con, "minha_tabela", derived_sql=None)
    assert cols == ["id", "valor"]


def test_table_column_names_derived_sql() -> None:
    con = duckdb.connect()
    con.execute('CREATE TABLE "base" AS SELECT 1 AS a, 2 AS b')
    cols = table_column_names(con, "base", derived_sql='SELECT a FROM "base"')
    assert cols == ["a"]

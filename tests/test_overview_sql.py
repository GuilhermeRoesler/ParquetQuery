from __future__ import annotations

from pq.overview.sql import (
    build_classificatory_overview_sql,
    build_classificatory_overview_summary_sql,
    build_numeric_overview_sql,
    column_type_category,
)


def test_column_type_category() -> None:
    assert column_type_category("BIGINT") == "numeric"
    assert column_type_category("VARCHAR") == "text"
    assert column_type_category("TIMESTAMP") == "date"


def test_build_classificatory_overview_sql() -> None:
    sql = build_classificatory_overview_sql("t", "status", None)
    assert '"status"' in sql
    assert 'FROM "t"' in sql
    assert "GROUP BY" in sql


def test_build_classificatory_overview_summary_sql() -> None:
    sql = build_classificatory_overview_summary_sql("t", "status", None)
    assert "distinct_count" in sql
    assert "total_rows" in sql


def test_build_numeric_overview_sql() -> None:
    sql = build_numeric_overview_sql("t", "valor", "AVG", "DOUBLE", None)
    assert "AVG" in sql
    assert '"valor"' in sql


def test_clear_overview_cache() -> None:
    from pq.db.cached import clear_overview_cache

    clear_overview_cache()

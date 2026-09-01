from pq.db.derived import build_derived_select, work_from_clause, working_sql


def test_work_from_clause_raw_table() -> None:
    assert work_from_clause("tabela", None) == '"tabela"'


def test_work_from_clause_derived() -> None:
    derived = 'SELECT * FROM "tabela"'
    assert work_from_clause("tabela", derived) == f"({derived}) __work__"


def test_build_derived_select() -> None:
    sql = build_derived_select("t", '*, 1 AS "x"', None)
    assert sql == 'SELECT *, 1 AS "x" FROM "t"'


def test_working_sql() -> None:
    assert working_sql("t", None) == 'SELECT * FROM "t"'
    assert working_sql("t", "SELECT a FROM t") == "SELECT a FROM t"

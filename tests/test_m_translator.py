from pq.translators.m import m_parameter_names, translate_m_to_sql


def test_translate_select_rows() -> None:
    m_code = """
RangeStart = #date(2025, 1, 1),
#"Filtrado" = Table.SelectRows(Vendas, each [DATA] >= RangeStart),
"""
    sql = translate_m_to_sql(m_code, table_map={"Vendas": "vendas_loaded"})
    assert "WITH params AS" in sql
    assert '"Filtrado"' in sql
    assert "FROM vendas_loaded" in sql or 'FROM "vendas_loaded"' in sql


def test_m_parameter_names() -> None:
    m_code = """
RangeStart = #date(2025, 1, 1),
#"Filtrado" = Table.SelectRows(T, each [DATA] >= RangeStart),
"""
    params = m_parameter_names(m_code)
    assert "RangeStart" in params

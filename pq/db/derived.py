"""SQL derivado — colunas calculadas e base de trabalho."""


def work_from_clause(table: str, derived_sql: str | None) -> str:
    """Fragmento para cláusula FROM: tabela DuckDB ou subquery derivada."""
    if derived_sql:
        return f"({derived_sql}) __work__"
    return f'"{table}"'


def build_derived_select(table: str, select_expr: str, derived_sql: str | None) -> str:
    return f"SELECT {select_expr} FROM {work_from_clause(table, derived_sql)}"


def working_sql(table: str, derived_sql: str | None) -> str:
    """SQL completo da base de trabalho (para export/DESCRIBE)."""
    if derived_sql:
        return derived_sql
    return f'SELECT * FROM "{table}"'


def default_preview_sql(table: str, derived_sql: str | None, *, limit: int = 100) -> str:
    return f"SELECT * FROM {work_from_clause(table, derived_sql)} LIMIT {limit}"

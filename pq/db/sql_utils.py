"""Utilitários SQL genéricos."""


def strip_sql(sql: str) -> str:
    """Remove espaços e ponto-e-vírgula final."""
    return sql.strip().rstrip(";")

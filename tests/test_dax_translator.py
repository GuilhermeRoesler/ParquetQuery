import pytest

from pq.translators.dax import normalize_power_formula, translate_dax_expression, translate_power_column
from pq.translators.errors import ParseError


def test_translate_if_simple() -> None:
    sql = translate_dax_expression('IF([valor] > 100, "Alto", "Baixo")')
    assert "CASE WHEN" in sql
    assert "'Alto'" in sql
    assert "'Baixo'" in sql


def test_translate_power_column() -> None:
    name, expr = translate_power_column("Total = [a] + [b]")
    assert name == "Total"
    assert '"a"' in expr
    assert '"b"' in expr


def test_normalize_strips_comments() -> None:
    text = "Col = 1 -- comentário"
    assert normalize_power_formula(text) == "Col = 1"


def test_invalid_formula_raises() -> None:
    with pytest.raises(ParseError):
        translate_power_column("= expressão sem nome")

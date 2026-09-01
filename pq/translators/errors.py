"""Erros compartilhados dos tradutores DAX e M."""

from __future__ import annotations


class ParseError(ValueError):
    """Erro de parsing em fórmula DAX ou script M."""

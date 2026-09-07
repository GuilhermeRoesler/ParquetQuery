"""Utilitários de exportação."""

from __future__ import annotations


def export_extension(fmt: str) -> str:
    return {"CSV": "csv", "XLSX": "xlsx", "Parquet": "parquet"}[fmt]

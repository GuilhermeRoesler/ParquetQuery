"""Exportação para bytes e disco."""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def df_to_xlsx_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    return buf.getvalue()


def df_to_parquet_bytes(df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    return buf.getvalue()


def export_extension(fmt: str) -> str:
    return {"CSV": "csv", "XLSX": "xlsx", "Parquet": "parquet"}[fmt]


def export_to_bytes(df: pd.DataFrame, fmt: str) -> tuple[bytes, str]:
    if fmt == "CSV":
        return df_to_csv_bytes(df), "text/csv"
    if fmt == "Parquet":
        return df_to_parquet_bytes(df), "application/vnd.apache.parquet"
    return df_to_xlsx_bytes(df), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def save_to_data(
    df: pd.DataFrame,
    dest: Path,
    fmt: str,
    *,
    overwrite: bool,
) -> Path:
    if dest.exists() and not overwrite:
        raise FileExistsError(f"O arquivo `{dest.name}` já existe.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "CSV":
        df.to_csv(dest, index=False, encoding="utf-8-sig")
    elif fmt == "Parquet":
        df.to_parquet(dest, index=False, engine="pyarrow")
    else:
        df.to_excel(dest, index=False, engine="openpyxl")
    return dest

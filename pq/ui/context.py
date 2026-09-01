"""Contexto compartilhado entre abas da UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd


@dataclass(frozen=True)
class WorkContext:
    con: duckdb.DuckDBPyConnection
    data_dir: Path
    active: str
    loaded: list[str]
    current_base: str
    schema_df: pd.DataFrame
    work_schema_df: pd.DataFrame
    col_names: list[str]
    col_types: dict[str, str]
    work_from_clause: str
    work_sql: str
    derived_sql: str | None
    has_derived: bool

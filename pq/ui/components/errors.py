"""Helpers de erro na UI."""

from __future__ import annotations

import streamlit as st


def show_db_error(exc: BaseException, *, prefix: str = "Erro") -> None:
    st.error(f"{prefix}: {exc}")

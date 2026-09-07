"""Branding — ícone do app (favicon + logo da sidebar)."""

from __future__ import annotations

import streamlit as st

from pq.config import BASE

ICON_PATH = BASE / "assets" / "icon.png"


def icon_file() -> str | None:
    return str(ICON_PATH) if ICON_PATH.is_file() else None


def apply_page_logo() -> None:
    """Um único ícone na UI: logo no chrome da sidebar."""
    path = icon_file()
    if path:
        st.logo(path, size="large")

"""Editor SQL com autocomplete."""

from __future__ import annotations

import streamlit as st

from pq.config import DUCKDB_FUNCTIONS, SQL_KEYWORDS


SQL_EDITOR_OPTIONS = {
    "enableBasicAutocompletion": True,
    "enableLiveAutocompletion": True,
}

SQL_EDITOR_PROPS = {
    "style": {
        "minHeight": "180px",
        "borderRadius": "0 0 8px 8px",
    },
}

SQL_EDITOR_COMPONENT_PROPS = {
    "style": {"overflow": "visible"},
    "css": """
        & {
            overflow: visible !important;
            padding-bottom: 14rem;
        }
    """,
    "globalCSS": """
        html, body {
            overflow: visible !important;
        }
        .ace_autocomplete {
            z-index: 999999 !important;
            max-height: min(280px, 45vh);
        }
    """,
}


def inject_sql_editor_layout_css() -> None:
    """Evita que abas Streamlit cortem o popup de autocomplete do iframe."""
    st.markdown(
        """
        <style>
        div[data-testid="stTabs"] [data-baseweb="tab-panel"] {
            overflow: visible !important;
        }
        div[data-testid="stTabs"] [data-baseweb="tab-panel"] > div {
            overflow: visible !important;
        }
        div[data-testid="stCustomComponentV1"] {
            overflow: visible !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def build_sql_completions(
    tables: list[str],
    schemas: dict[str, list[str]],
) -> list[dict[str, str | int]]:
    completions: list[dict[str, str | int]] = []
    seen: set[str] = set()

    def add(caption: str, value: str, score: int, meta: str) -> None:
        if value in seen:
            return
        seen.add(value)
        completions.append({"caption": caption, "value": value, "score": score, "meta": meta})

    for kw in SQL_KEYWORDS:
        add(kw, kw, 400, "keyword")
    for fn in DUCKDB_FUNCTIONS:
        add(fn, fn, 300, "função")
    for table in tables:
        add(table, f'"{table}"', 500, "tabela")
    for table, cols in schemas.items():
        for col in cols:
            quoted = f'"{col}"'
            add(f"{table}.{col}", quoted, 450, "coluna")
            add(col, quoted, 420, "coluna")
    return completions

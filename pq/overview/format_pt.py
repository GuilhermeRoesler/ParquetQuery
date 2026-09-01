"""Formatação numérica pt-BR."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd


def _format_int_pt(n: int) -> str:
    s = str(abs(n))
    parts: list[str] = []
    while s:
        parts.append(s[-3:])
        s = s[:-3]
    formatted = ".".join(reversed(parts))
    return f"-{formatted}" if n < 0 else formatted


def format_number_pt(value: object, *, max_decimals: int = 6) -> str:
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except TypeError:
        pass
    if isinstance(value, datetime):
        if value.hour or value.minute or value.second:
            return value.strftime("%d/%m/%Y %H:%M:%S")
        return value.strftime("%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")

    num = float(value) if isinstance(value, (int, float, str)) else float(str(value))
    if num == int(num) and abs(num) < 1e18:
        return _format_int_pt(int(num))

    sign = "-" if num < 0 else ""
    num = abs(num)
    raw = f"{num:.{max_decimals}f}".rstrip("0").rstrip(".")
    int_s, _, dec_s = raw.partition(".")
    int_formatted = _format_int_pt(int(int_s or "0"))
    if dec_s:
        return f"{sign}{int_formatted},{dec_s}"
    return f"{sign}{int_formatted}"

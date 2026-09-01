from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from pq.overview.format_pt import format_number_pt


def test_format_number_pt_none() -> None:
    assert format_number_pt(None) == "—"


def test_format_number_pt_nan() -> None:
    assert format_number_pt(float("nan")) == "—"


def test_format_number_pt_integer() -> None:
    assert format_number_pt(1234567) == "1.234.567"
    assert format_number_pt(-42) == "-42"


def test_format_number_pt_decimal() -> None:
    assert format_number_pt(1234.5) == "1.234,5"


def test_format_number_pt_date() -> None:
    assert format_number_pt(date(2024, 3, 15)) == "15/03/2024"


def test_format_number_pt_datetime() -> None:
    assert format_number_pt(datetime(2024, 3, 15, 14, 30, 0)) == "15/03/2024 14:30:00"


def test_format_number_pt_pandas_na() -> None:
    assert format_number_pt(pd.NA) == "—"

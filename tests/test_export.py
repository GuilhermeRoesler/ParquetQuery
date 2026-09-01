import pandas as pd

from pq.export.io import export_extension, export_to_bytes


def test_export_extension() -> None:
    assert export_extension("Parquet") == "parquet"
    assert export_extension("CSV") == "csv"


def test_export_csv_bytes() -> None:
    df = pd.DataFrame({"a": [1, 2]})
    data, mime = export_to_bytes(df, "CSV")
    assert mime == "text/csv"
    assert b"a" in data

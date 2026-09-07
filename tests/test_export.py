from pq.export.io import export_extension


def test_export_extension() -> None:
    assert export_extension("Parquet") == "parquet"
    assert export_extension("CSV") == "csv"
    assert export_extension("XLSX") == "xlsx"

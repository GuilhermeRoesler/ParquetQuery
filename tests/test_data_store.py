from __future__ import annotations

from pathlib import Path

from pq.storage.data_store import (
    base_name_from,
    next_available_version,
    record_version,
    version_from_stem,
    versioned_stem,
)


def test_version_from_stem_original() -> None:
    assert version_from_stem("vendas") is None
    assert base_name_from("vendas") == "vendas"


def test_version_from_stem_numbered() -> None:
    assert version_from_stem("vendas_v3") == 3
    assert base_name_from("vendas_v3") == "vendas"
    assert versioned_stem("vendas", 4) == "vendas_v4"


def test_next_available_version(tmp_path: Path) -> None:
    assert next_available_version(tmp_path, "base") == 1
    record_version(
        tmp_path,
        "base",
        1,
        filename="base_v1.parquet",
        fmt="Parquet",
        source_table="base",
        export_source="test",
        overwrite=False,
    )
    assert next_available_version(tmp_path, "base") == 2

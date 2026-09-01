from __future__ import annotations

import json
from pathlib import Path

import pytest

from pq.storage.data_store import (
    build_timeline,
    load_manifest,
    manifest_corrupt_message,
    manifest_is_corrupt,
    safe_data_path,
)


def test_load_manifest_missing(tmp_path: Path) -> None:
    manifest = load_manifest(tmp_path)
    assert manifest == {"bases": {}}
    assert not manifest_is_corrupt(manifest)


def test_load_manifest_corrupt(tmp_path: Path) -> None:
    (tmp_path / "_manifest.json").write_text("{ invalid", encoding="utf-8")
    manifest = load_manifest(tmp_path)
    assert manifest_is_corrupt(manifest)
    assert "invalid" in manifest_corrupt_message(manifest).lower() or manifest_corrupt_message(
        manifest
    )


def test_safe_data_path_ok(tmp_path: Path) -> None:
    dest = safe_data_path(tmp_path, "vendas_v1", "parquet")
    assert dest.parent == tmp_path.resolve()
    assert dest.name == "vendas_v1.parquet"


def test_safe_data_path_rejects_traversal(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"inválido|fora"):
        safe_data_path(tmp_path, "../escape", "csv")


def test_build_timeline_with_original(tmp_path: Path) -> None:
    (tmp_path / "vendas.parquet").write_bytes(b"")
    timeline = build_timeline(tmp_path, "vendas")
    assert len(timeline) == 1
    assert timeline[0]["label"] == "original"


def test_save_manifest_strips_corrupt_flags(tmp_path: Path) -> None:
    from pq.storage.data_store import save_manifest

    save_manifest(tmp_path, {"bases": {}, "_corrupt": True, "_corrupt_message": "x"})
    data = json.loads((tmp_path / "_manifest.json").read_text(encoding="utf-8"))
    assert "_corrupt" not in data

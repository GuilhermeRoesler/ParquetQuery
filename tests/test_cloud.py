from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pq.config import is_cloud_mode
from pq.storage.cloud import list_demo_files, sanitize_upload_stem, save_uploaded_file


class _FakeUpload:
    def __init__(self, name: str, data: bytes) -> None:
        self.name = name
        self._data = data

    @property
    def size(self) -> int:
        return len(self._data)

    def getvalue(self) -> bytes:
        return self._data


def test_is_cloud_mode_env_override() -> None:
    with patch.dict("os.environ", {"PQ_CLOUD_MODE": "1"}, clear=False):
        assert is_cloud_mode() is True
    with patch.dict("os.environ", {"PQ_CLOUD_MODE": "0"}, clear=False):
        assert is_cloud_mode() is False


def test_is_cloud_mode_streamlit_runtime() -> None:
    with patch.dict("os.environ", {"STREAMLIT_RUNTIME_ENVIRONMENT": "cloud"}, clear=False):
        assert is_cloud_mode() is True


def test_sanitize_upload_stem() -> None:
    assert sanitize_upload_stem("vendas.parquet") == "vendas"
    assert sanitize_upload_stem("meu arquivo (1).csv") == "meu_arquivo_1"


def test_sanitize_upload_stem_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        sanitize_upload_stem("..")
    with pytest.raises(ValueError):
        sanitize_upload_stem("   ")


def test_save_uploaded_file(tmp_path: Path) -> None:
    upload = _FakeUpload("demo.csv", b"a,b\n1,2\n")
    dest = save_uploaded_file(tmp_path, upload)
    assert dest.name == "demo.csv"
    assert dest.read_bytes() == b"a,b\n1,2\n"


def test_save_uploaded_file_rejects_large(tmp_path: Path) -> None:
    upload = _FakeUpload("big.parquet", b"x" * (50 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="limite"):
        save_uploaded_file(tmp_path, upload)


def test_list_demo_files_includes_committed_sample() -> None:
    names = [path.name for path in list_demo_files()]
    assert "vendas_demo.parquet" in names

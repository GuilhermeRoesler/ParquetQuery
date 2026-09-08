from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pq.config import is_cloud_mode
from pq.storage.cloud import list_demo_files, sanitize_upload_stem, save_uploaded_file


class _FakeUpload:
    def __init__(self, name: str, data: bytes, size: int | None = None) -> None:
        self.name = name
        self._data = data
        self._size = size

    @property
    def size(self) -> int:
        return len(self._data) if self._size is None else self._size

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


def test_is_cloud_mode_streamlit_sharing() -> None:
    with patch.dict("os.environ", {"STREAMLIT_SHARING": "true"}, clear=False):
        assert is_cloud_mode() is True


def test_is_cloud_mode_mount_src(monkeypatch: pytest.MonkeyPatch) -> None:
    class _RepoRoot:
        def resolve(self) -> Path:
            return Path("/mount/src/parquet-query")

    monkeypatch.setattr("pq.config.BASE", _RepoRoot())
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
    upload = _FakeUpload("big.parquet", b"x", size=50 * 1024 * 1024 + 1)
    with pytest.raises(ValueError, match="limite"):
        save_uploaded_file(tmp_path, upload)


def test_save_uploaded_file_local_limit(tmp_path: Path) -> None:
    from pq.config import LOCAL_UPLOAD_MAX_BYTES

    upload = _FakeUpload("ok.csv", b"a,b\n1,2\n")
    dest = save_uploaded_file(tmp_path, upload, max_bytes=LOCAL_UPLOAD_MAX_BYTES)
    assert dest.read_bytes() == b"a,b\n1,2\n"

    too_big = _FakeUpload("huge.parquet", b"x", size=LOCAL_UPLOAD_MAX_BYTES + 1)
    with pytest.raises(ValueError, match="limite"):
        save_uploaded_file(tmp_path, too_big, max_bytes=LOCAL_UPLOAD_MAX_BYTES)


def test_list_demo_files_includes_committed_sample() -> None:
    names = [path.name for path in list_demo_files()]
    assert "vendas_demo.parquet" in names
    assert "clientes_demo.parquet" in names


def test_demo_source_label() -> None:
    from pq.storage.cloud import demo_source_label

    assert "vendas" in demo_source_label(Path("vendas_demo.parquet")).lower()
    assert "clientes" in demo_source_label(Path("clientes_demo.parquet")).lower()


def test_demo_sql_recipes_mention_join() -> None:
    from pq.translators import normalize_power_formula, translate_m_to_sql, translate_power_column
    from pq.ui.demo_recipes import DEMO_DAX_EXAMPLE, DEMO_M_EXAMPLE, demo_sql_recipes

    sql = demo_sql_recipes()
    assert "JOIN" in sql
    assert "valor_linha" in sql
    translate_m_to_sql(DEMO_M_EXAMPLE, table_map={"vendas_demo": "vendas_demo"})
    translate_power_column(normalize_power_formula(DEMO_DAX_EXAMPLE))

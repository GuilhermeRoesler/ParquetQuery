"""Testes do bootstrap Windows lite e prioridade de Python no tray."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_BOOTSTRAP = _SCRIPTS / "windows_lite_bootstrap.py"
_LAUNCHER = _SCRIPTS / "windows_tray_launcher.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bootstrap = _load("windows_lite_bootstrap", _BOOTSTRAP)
tray = _load("windows_tray_launcher", _LAUNCHER)


def test_check_python_version_ok() -> None:
    bootstrap.check_python_version((3, 10, 0))
    bootstrap.check_python_version((3, 12, 1))


def test_check_python_version_rejects_old() -> None:
    with pytest.raises(SystemExit, match=r"3\.10"):
        bootstrap.check_python_version((3, 9, 13))


def test_venv_ready_false_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "nope" / "python.exe"
    monkeypatch.setattr(bootstrap, "VENV_PYTHON", missing)
    assert bootstrap.venv_ready(missing) is False


def test_python_exe_prefers_venv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray, "ROOT", tmp_path)
    venv_py = tmp_path / ".venv" / "Scripts" / "python.exe"
    venv_py.parent.mkdir(parents=True)
    venv_py.write_bytes(b"")
    embedded = tmp_path / "python" / "python.exe"
    embedded.parent.mkdir(parents=True)
    embedded.write_bytes(b"")
    assert tray._python_exe() == venv_py


def test_python_exe_prefers_embedded_without_venv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(tray, "ROOT", tmp_path)
    embedded = tmp_path / "python" / "python.exe"
    embedded.parent.mkdir(parents=True)
    embedded.write_bytes(b"")
    assert tray._python_exe() == embedded

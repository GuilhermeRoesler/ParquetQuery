"""Testes unitários do launcher Windows (funções puras / rede local)."""

from __future__ import annotations

import importlib.util
import socket
import threading
import time
from pathlib import Path

import pytest

_LAUNCHER = Path(__file__).resolve().parents[1] / "scripts" / "windows_tray_launcher.py"


def _load_tray():
    spec = importlib.util.spec_from_file_location("windows_tray_launcher", _LAUNCHER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tray = _load_tray()


def test_app_url() -> None:
    assert tray.app_url(8501) == "http://127.0.0.1:8501"


def test_wait_for_port_success() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    sock.listen(1)
    port = sock.getsockname()[1]
    try:
        assert tray.wait_for_port(port, timeout=2.0, interval=0.05) is True
    finally:
        sock.close()


def test_wait_for_port_timeout() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    assert tray.wait_for_port(port, timeout=0.3, interval=0.05) is False


def test_read_write_saved_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = tmp_path / ".runtime"
    monkeypatch.setattr(tray, "RUNTIME_DIR", runtime)
    monkeypatch.setattr(tray, "PORT_PATH", runtime / "port")
    assert tray.read_saved_port() is None
    tray.write_saved_port(8502)
    assert tray.read_saved_port() == 8502
    tray.clear_saved_port()
    assert tray.read_saved_port() is None


def test_ensure_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tray, "ROOT", tmp_path)
    data = tray.ensure_data_dir()
    assert data.is_dir()
    assert data == tmp_path / "data"


def test_wait_for_port_appears_later() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    def _listen_later() -> None:
        time.sleep(0.15)
        later = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        later.bind(("127.0.0.1", port))
        later.listen(1)
        time.sleep(0.5)
        later.close()

    threading.Thread(target=_listen_later, daemon=True).start()
    assert tray.wait_for_port(port, timeout=2.0, interval=0.05) is True

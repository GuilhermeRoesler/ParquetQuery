"""Launcher Windows: Streamlit em background + ícone na bandeja do sistema."""

from __future__ import annotations

import atexit
import contextlib
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = ROOT / ".runtime"
LOCK_PATH = RUNTIME_DIR / "launcher.lock"
PORT_PATH = RUNTIME_DIR / "port"
ICON_PATH = ROOT / "assets" / "icon.png"
DEFAULT_PORT = 8501
CREATE_NO_WINDOW = 0x08000000

_lock_fh: object | None = None


def _message_box(text: str, title: str = "Parquet Query") -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)  # type: ignore[attr-defined]
    except Exception:
        print(text, file=sys.stderr)


def _python_exe() -> Path:
    """Prioridade: .venv (pacote lite) → Python embutido (full) → interpretador atual."""
    venv = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv.is_file():
        return venv
    embedded = ROOT / "python" / "python.exe"
    if embedded.is_file():
        return embedded
    return Path(sys.executable)


def ensure_data_dir() -> Path:
    data_dir = ROOT / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def app_url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def wait_for_port(port: int, timeout: float = 90.0, interval: float = 0.25) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(interval)
    return False


def read_saved_port() -> int | None:
    try:
        text = PORT_PATH.read_text(encoding="utf-8").strip()
        port = int(text)
    except (OSError, ValueError):
        return None
    return port if 1 <= port <= 65535 else None


def write_saved_port(port: int) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    PORT_PATH.write_text(str(port), encoding="utf-8")


def clear_saved_port() -> None:
    with contextlib.suppress(OSError):
        PORT_PATH.unlink(missing_ok=True)


def try_acquire_lock() -> bool:
    """Trava exclusiva por instalação (arquivo em ROOT/.runtime)."""
    global _lock_fh
    import msvcrt

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK_PATH, "a+b")  # noqa: SIM115
    try:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        fh.close()
        return False
    _lock_fh = fh
    return True


def release_lock() -> None:
    global _lock_fh
    import msvcrt

    fh = _lock_fh
    _lock_fh = None
    if fh is None:
        return
    try:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass
    with contextlib.suppress(OSError):
        fh.close()


def find_free_port(start: int = DEFAULT_PORT, limit: int = 50) -> int:
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from find_free_port import find_free_port as _find

    return _find(start, limit)


def start_streamlit(port: int) -> subprocess.Popen[bytes]:
    python = _python_exe()
    app_py = ROOT / "app.py"
    if not app_py.is_file():
        raise FileNotFoundError(f"app.py não encontrado em {ROOT}")
    creationflags = CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.Popen(
        [
            str(python),
            "-m",
            "streamlit",
            "run",
            str(app_py),
            "--server.headless",
            "true",
            "--server.port",
            str(port),
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )


def stop_streamlit(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW,
        )
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def open_browser(port: int) -> None:
    webbrowser.open(app_url(port))


def open_data_folder() -> None:
    data_dir = ensure_data_dir()
    os.startfile(str(data_dir))  # type: ignore[attr-defined]


def _load_tray_image():
    from PIL import Image

    if ICON_PATH.is_file():
        return Image.open(ICON_PATH)
    return Image.new("RGB", (64, 64), color=(30, 120, 180))


def create_tray_icon(port: int, on_quit: Callable[[], None]):
    """Monta o Icon da bandeja (chamar icon.run() para bloquear)."""
    import pystray
    from pystray import MenuItem as Item

    url = app_url(port)

    def _open(_icon: object, _item: object) -> None:
        open_browser(port)

    def _data(_icon: object, _item: object) -> None:
        open_data_folder()

    def _quit(icon: object, _item: object) -> None:
        on_quit()
        icon.stop()  # type: ignore[attr-defined]

    menu = pystray.Menu(
        Item(f"Abrir no navegador ({url})", _open, default=True),
        Item("Abrir pasta data", _data),
        Item("Sair", _quit),
    )
    return pystray.Icon("parquet-query", _load_tray_image(), "Parquet Query", menu)


def main() -> int:
    if not try_acquire_lock():
        existing = read_saved_port()
        if existing is not None and wait_for_port(existing, timeout=2.0):
            open_browser(existing)
            return 0
        _message_box(
            "O Parquet Query já parece estar em execução, mas a porta não respondeu.\n"
            "Encerre o ícone na bandeja ou aguarde e tente de novo."
        )
        return 1

    ensure_data_dir()

    try:
        import pystray  # noqa: F401
        from PIL import Image  # noqa: F401
    except ImportError:
        release_lock()
        _message_box(
            "Dependências da bandeja ausentes (pystray/Pillow).\n"
            "Reinstale o pacote portátil ou o instalador."
        )
        return 1

    try:
        port = find_free_port(DEFAULT_PORT)
    except SystemExit as exc:
        release_lock()
        _message_box(str(exc))
        return 1

    write_saved_port(port)
    streamlit_proc: subprocess.Popen[bytes] | None = None

    def cleanup() -> None:
        stop_streamlit(streamlit_proc)
        clear_saved_port()
        release_lock()

    try:
        streamlit_proc = start_streamlit(port)
    except Exception as exc:
        cleanup()
        _message_box(f"Não foi possível iniciar o Streamlit:\n{exc}")
        return 1

    atexit.register(cleanup)

    if not wait_for_port(port):
        cleanup()
        _message_box(
            "O servidor não respondeu a tempo.\n"
            f"Verifique se a porta {port} está bloqueada e tente novamente."
        )
        return 1

    open_browser(port)

    try:
        icon = create_tray_icon(port, cleanup)
    except Exception as exc:
        cleanup()
        _message_box(f"Erro na bandeja do sistema:\n{exc}")
        return 1

    def stop_icon_if_server_dies() -> None:
        assert streamlit_proc is not None
        streamlit_proc.wait()
        with contextlib.suppress(Exception):
            icon.stop()

    threading.Thread(target=stop_icon_if_server_dies, daemon=True).start()

    try:
        icon.run()
    except Exception as exc:
        cleanup()
        _message_box(f"Erro na bandeja do sistema:\n{exc}")
        return 1

    cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

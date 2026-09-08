"""Bootstrap do pacote Windows lite: Python do sistema + .venv + bandeja.

Na 1ª execução cria ``.venv``, instala ``requirements-portable-win.txt`` e
entrega o controle a ``windows_tray_launcher.py`` via ``pythonw``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = ROOT / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
VENV_PYTHONW = VENV_DIR / "Scripts" / "pythonw.exe"
REQUIREMENTS = ROOT / "requirements-portable-win.txt"
TRAY_LAUNCHER = ROOT / "scripts" / "windows_tray_launcher.py"
CREATE_NO_WINDOW = 0x08000000
MIN_VERSION = (3, 10)


def _message_box(text: str, title: str = "Parquet Query") -> None:
    try:
        import ctypes

        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)  # type: ignore[attr-defined]
    except Exception:
        print(text, file=sys.stderr)


def _print(msg: str) -> None:
    print(msg, flush=True)


def check_python_version(version_info: tuple[int, ...] = sys.version_info) -> None:
    if version_info[:2] < MIN_VERSION:
        major, minor = MIN_VERSION
        raise SystemExit(
            f"Python {major}.{minor}+ é necessário (encontrado "
            f"{version_info[0]}.{version_info[1]})."
        )


def venv_ready(python: Path = VENV_PYTHON) -> bool:
    """True se o venv existe e importa as deps do pacote lite."""
    if not python.is_file():
        return False
    probe = subprocess.run(
        [str(python), "-c", "import streamlit, pystray, PIL"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return probe.returncode == 0


def create_venv(base_python: str | None = None) -> None:
    exe = base_python or sys.executable
    _print(f"Criando ambiente virtual em {VENV_DIR} ...")
    subprocess.run([exe, "-m", "venv", str(VENV_DIR)], cwd=str(ROOT), check=True)


def install_requirements(python: Path = VENV_PYTHON) -> None:
    if not REQUIREMENTS.is_file():
        raise FileNotFoundError(f"Arquivo ausente: {REQUIREMENTS.name}")
    _print("Instalando dependências (pode levar alguns minutos) ...")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--upgrade", "pip"],
        cwd=str(ROOT),
        check=True,
    )
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        cwd=str(ROOT),
        check=True,
    )


def ensure_venv() -> Path:
    """Garante ``.venv`` com deps; devolve o ``python.exe`` do venv."""
    if venv_ready():
        return VENV_PYTHON
    if not VENV_PYTHON.is_file():
        create_venv()
    if not VENV_PYTHON.is_file():
        raise FileNotFoundError(f"python.exe do venv não encontrado em {VENV_DIR}")
    install_requirements()
    if not venv_ready():
        raise RuntimeError(
            "Dependências instaladas, mas streamlit/pystray/Pillow não importam. "
            "Verifique a saída do pip acima."
        )
    return VENV_PYTHON


def resolve_tray_python() -> Path:
    if VENV_PYTHONW.is_file():
        return VENV_PYTHONW
    if VENV_PYTHON.is_file():
        return VENV_PYTHON
    raise FileNotFoundError(f"Interpretador do venv não encontrado em {VENV_DIR}")


def launch_tray() -> None:
    if not TRAY_LAUNCHER.is_file():
        raise FileNotFoundError(f"Launcher ausente: {TRAY_LAUNCHER}")
    python = resolve_tray_python()
    creationflags = CREATE_NO_WINDOW if os.name == "nt" else 0
    subprocess.Popen(
        [str(python), str(TRAY_LAUNCHER)],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )


def main() -> int:
    try:
        check_python_version()
        (ROOT / "data").mkdir(parents=True, exist_ok=True)
        first_run = not venv_ready()
        if first_run:
            _print("Parquet Query (pacote lite)")
            _print("Primeira execução: configurando ambiente local...")
            _print("")
        ensure_venv()
        if first_run:
            _print("")
            _print("Ambiente pronto. Abrindo o app...")
        launch_tray()
        return 0
    except Exception as exc:
        msg = str(exc)
        _print(f"[ERRO] {msg}")
        _message_box(
            "Não foi possível preparar o Parquet Query (pacote lite).\n\n"
            f"{msg}\n\n"
            "Requisitos: Python 3.10+ no PATH e internet na 1ª execução.\n"
            "Alternativa sem Python: use o instalador win64-setup.exe completo."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

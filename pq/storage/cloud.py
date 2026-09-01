"""Arquivos e uploads no modo vitrine (Streamlit Community Cloud)."""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import Protocol, cast

import streamlit as st

from pq.config import CLOUD_UPLOAD_MAX_BYTES, DEMO_DIR, LOADABLE_EXTENSIONS

_UPLOAD_STEM_RE = re.compile(r"[^A-Za-z0-9._-]+")


class UploadedFileLike(Protocol):
    name: str
    size: int | None

    def getvalue(self) -> bytes: ...


def cloud_upload_dir() -> Path:
    """Diretório temporário por sessão para uploads e exports efêmeros."""
    if "cloud_upload_dir" not in st.session_state:
        st.session_state.cloud_upload_dir = Path(tempfile.mkdtemp(prefix="pq_upload_"))
    return cast(Path, st.session_state.cloud_upload_dir)


def sanitize_upload_stem(name: str) -> str:
    """Nome seguro (sem extensão) para arquivo enviado pelo browser."""
    stem = Path(name).stem.strip()
    if not stem or stem in {".", ".."}:
        raise ValueError("Nome de arquivo inválido.")
    safe = _UPLOAD_STEM_RE.sub("_", stem).strip("._")
    if not safe or safe in {".", ".."}:
        raise ValueError("Nome de arquivo inválido.")
    return safe[:120]


def list_demo_files() -> list[Path]:
    if not DEMO_DIR.is_dir():
        return []
    return sorted(
        path
        for path in DEMO_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in LOADABLE_EXTENSIONS
    )


def list_upload_files(upload_dir: Path) -> list[Path]:
    if not upload_dir.is_dir():
        return []
    return sorted(
        path
        for path in upload_dir.iterdir()
        if path.is_file() and path.suffix.lower() in LOADABLE_EXTENSIONS
    )


def list_cloud_sources(upload_dir: Path) -> list[tuple[Path, str]]:
    """(caminho, rótulo) — demo ou upload."""
    sources: list[tuple[Path, str]] = [(path, "exemplo") for path in list_demo_files()]
    sources.extend((path, "enviado") for path in list_upload_files(upload_dir))
    return sources


def save_uploaded_file(upload_dir: Path, uploaded_file: UploadedFileLike) -> Path:
    """Grava upload no diretório da sessão; rejeita arquivos grandes ou inválidos."""
    if uploaded_file.size is None or uploaded_file.size <= 0:
        raise ValueError("Arquivo vazio.")
    if uploaded_file.size > CLOUD_UPLOAD_MAX_BYTES:
        limit_mb = CLOUD_UPLOAD_MAX_BYTES // (1024 * 1024)
        raise ValueError(f"Arquivo excede o limite de {limit_mb} MB na versão online.")

    ext = Path(uploaded_file.name).suffix.lower()
    if ext not in LOADABLE_EXTENSIONS:
        raise ValueError("Formato não suportado. Use `.parquet` ou `.csv`.")

    stem = sanitize_upload_stem(uploaded_file.name)
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"{stem}{ext}"
    dest.write_bytes(uploaded_file.getvalue())
    return dest


def process_sidebar_uploads(upload_dir: Path) -> int:
    """Processa novos arquivos do file_uploader; retorna quantos foram salvos."""
    uploaded = st.session_state.get("cloud_file_uploader")
    if not uploaded:
        return 0

    if "cloud_processed_uploads" not in st.session_state:
        st.session_state.cloud_processed_uploads = set()

    saved = 0
    for item in uploaded:
        signature = (item.name, item.size)
        if signature in st.session_state.cloud_processed_uploads:
            continue
        save_uploaded_file(upload_dir, item)
        st.session_state.cloud_processed_uploads.add(signature)
        saved += 1
    return saved

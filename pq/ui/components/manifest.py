"""Avisos de manifesto na UI."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from pq.storage import load_manifest, manifest_corrupt_message, manifest_is_corrupt


def warn_if_manifest_corrupt(data_dir: Path, *, for_export: bool = False) -> None:
    manifest = load_manifest(data_dir)
    if not manifest_is_corrupt(manifest):
        return
    detail = manifest_corrupt_message(manifest)
    if for_export:
        st.warning(
            f"`_manifest.json` corrompido: {detail}. A exportação recriará o manifesto ao salvar."
        )
    else:
        st.warning(
            f"`_manifest.json` corrompido ou inválido: {detail}. "
            "Metadados de versão podem estar incompletos até a próxima exportação."
        )

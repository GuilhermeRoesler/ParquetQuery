"""Armazenamento versionado em `data/` com manifest de timeline."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION_SUFFIX_RE = re.compile(r"^(.+)_v(\d+)$")
DATA_EXTENSIONS = {".parquet", ".csv", ".xlsx"}
MANIFEST_NAME = "_manifest.json"


def base_name_from(stem: str) -> str:
    match = VERSION_SUFFIX_RE.match(stem)
    return match.group(1) if match else stem


def version_from_stem(stem: str) -> int | None:
    match = VERSION_SUFFIX_RE.match(stem)
    return int(match.group(2)) if match else None


def versioned_stem(base: str, version: int) -> str:
    return f"{base}_v{version}"


def manifest_path(data_dir: Path) -> Path:
    return data_dir / MANIFEST_NAME


def load_manifest(data_dir: Path) -> dict[str, Any]:
    path = manifest_path(data_dir)
    if not path.exists():
        return {"bases": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(data_dir: Path, manifest: dict[str, Any]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    manifest_path(data_dir).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def list_data_files(data_dir: Path) -> list[Path]:
    if not data_dir.exists():
        return []
    return sorted(
        path
        for path in data_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in DATA_EXTENSIONS
        and path.name != MANIFEST_NAME
    )


def files_for_version(data_dir: Path, base: str, version: int) -> list[Path]:
    stem = versioned_stem(base, version)
    return [path for path in list_data_files(data_dir) if path.stem == stem]


def version_exists(data_dir: Path, base: str, version: int) -> bool:
    return bool(files_for_version(data_dir, base, version))


def list_version_numbers(data_dir: Path, base: str) -> list[int]:
    versions: set[int] = set()
    prefix = f"{base}_v"
    for path in list_data_files(data_dir):
        if path.stem.startswith(prefix):
            parsed = version_from_stem(path.stem)
            if parsed is not None:
                versions.add(parsed)
    manifest = load_manifest(data_dir)
    for key in manifest.get("bases", {}).get(base, {}).get("versions", {}):
        if str(key).isdigit():
            versions.add(int(key))
    return sorted(versions)


def next_available_version(data_dir: Path, base: str) -> int:
    existing = list_version_numbers(data_dir, base)
    return (max(existing) + 1) if existing else 1


def original_file(data_dir: Path, base: str) -> Path | None:
    for ext in DATA_EXTENSIONS:
        path = data_dir / f"{base}{ext}"
        if path.exists() and version_from_stem(path.stem) is None and path.stem == base:
            return path
    return None


def build_timeline(data_dir: Path, base: str) -> list[dict[str, Any]]:
    manifest = load_manifest(data_dir)
    meta_versions = manifest.get("bases", {}).get(base, {}).get("versions", {})
    timeline: list[dict[str, Any]] = []

    orig = original_file(data_dir, base)
    if orig:
        timeline.append(
            {
                "version": 0,
                "label": "original",
                "stem": base,
                "files": [orig],
                "meta": meta_versions.get("0"),
            }
        )

    for version in list_version_numbers(data_dir, base):
        files = files_for_version(data_dir, base, version)
        timeline.append(
            {
                "version": version,
                "label": f"v{version}",
                "stem": versioned_stem(base, version),
                "files": files,
                "meta": meta_versions.get(str(version)),
            }
        )

    return timeline


def record_version(
    data_dir: Path,
    base: str,
    version: int,
    *,
    filename: str,
    fmt: str,
    source_table: str,
    export_source: str,
    overwrite: bool,
) -> None:
    manifest = load_manifest(data_dir)
    bases = manifest.setdefault("bases", {})
    entry = bases.setdefault(base, {"versions": {}})
    versions = entry["versions"]
    key = str(version)
    now = datetime.now(timezone.utc).isoformat()
    previous = versions.get(key, {})
    versions[key] = {
        "file": filename,
        "format": fmt,
        "source_table": source_table,
        "export_source": export_source,
        "created_at": previous.get("created_at", now),
        "updated_at": now,
        "overwrite": overwrite,
    }
    save_manifest(data_dir, manifest)


def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def migrate_legacy_dirs(data_dir: Path, base: Path) -> None:
    """Move `input/` e `output/` antigos para `data/` na primeira execução."""
    data_dir.mkdir(parents=True, exist_ok=True)
    legacy_input = base / "input"
    legacy_output = base / "output"

    if legacy_input.exists():
        for path in legacy_input.iterdir():
            if not path.is_file():
                continue
            dest = data_dir / path.name
            if not dest.exists():
                shutil.move(str(path), dest)
        if not any(legacy_input.iterdir()):
            legacy_input.rmdir()

    if legacy_output.exists():
        for path in legacy_output.iterdir():
            if not path.is_file() or path.suffix.lower() not in DATA_EXTENSIONS:
                continue
            stem = path.stem
            if stem.endswith("_export"):
                root = base_name_from(stem.removesuffix("_export"))
                version = next_available_version(data_dir, root)
                dest = data_dir / f"{versioned_stem(root, version)}{path.suffix.lower()}"
            else:
                dest = data_dir / path.name
            if not dest.exists():
                shutil.move(str(path), dest)
        if not any(legacy_output.iterdir()):
            legacy_output.rmdir()

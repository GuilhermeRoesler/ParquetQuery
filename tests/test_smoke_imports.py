from __future__ import annotations

import importlib
import sys


def test_import_app() -> None:
    importlib.import_module("app")


def test_import_core_packages() -> None:
    modules = [
        "pq.config",
        "pq.db.derived",
        "pq.db.sql_utils",
        "pq.db.queries",
        "pq.db.schema",
        "pq.export.io",
        "pq.export.query_export",
        "pq.storage.data_store",
        "pq.translators.dax",
        "pq.translators.m",
        "pq.overview.format_pt",
        "pq.overview.sql",
    ]
    for name in modules:
        importlib.import_module(name)


def test_import_app_not_in_sys_modules_before() -> None:
    """Garante que app.py é importável sem executar main."""
    sys.modules.pop("app", None)
    mod = importlib.import_module("app")
    assert hasattr(mod, "main")

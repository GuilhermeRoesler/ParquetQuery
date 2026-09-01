#!/usr/bin/env python3
"""Gera demo/vendas_demo.parquet para o modo vitrine (Streamlit Cloud)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
DEMO_DIR = BASE / "demo"
OUT = DEMO_DIR / "vendas_demo.parquet"

PRODUTOS = ["Notebook", "Mouse", "Teclado", "Monitor", "Webcam"]
CATEGORIAS = ["Informatica", "Perifericos", "Perifericos", "Informatica", "Perifericos"]
REGIOES = ["Sul", "Sudeste", "Nordeste", "Centro-Oeste", "Norte"]


def main() -> None:
    DEMO_DIR.mkdir(exist_ok=True)
    np.random.seed(42)
    n = 100
    df = pd.DataFrame(
        {
            "produto": [PRODUTOS[i % 5] for i in range(n)],
            "categoria": [CATEGORIAS[i % 5] for i in range(n)],
            "quantidade": np.random.randint(1, 20, n),
            "preco_unitario": np.round(np.random.uniform(29.9, 4500.0, n), 2),
            "data_venda": pd.date_range("2024-01-01", periods=n, freq="D"),
            "regiao": [REGIOES[i % 5] for i in range(n)],
        }
    )
    df.to_parquet(OUT, index=False)
    print(f"Gerado {OUT} ({len(df)} linhas, {OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Gera datasets de exemplo em demo/ para o modo vitrine (Streamlit Cloud)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
DEMO_DIR = BASE / "demo"
VENDAS_OUT = DEMO_DIR / "vendas_demo.parquet"
CLIENTES_OUT = DEMO_DIR / "clientes_demo.parquet"

PRODUTOS = [
    ("Notebook", "Informatica"),
    ("Mouse", "Perifericos"),
    ("Teclado", "Perifericos"),
    ("Monitor", "Informatica"),
    ("Webcam", "Perifericos"),
    ("Headset", "Perifericos"),
    ("SSD 1TB", "Informatica"),
    ("Cadeira gamer", "Moveis"),
]
REGIOES = ["Sul", "Sudeste", "Nordeste", "Centro-Oeste", "Norte"]
CANAIS = ["Loja", "E-commerce", "Marketplace", "Telefone"]
STATUS = ["pago", "pendente", "cancelado", "pago", "pago"]
SEGMENTOS = ["Enterprise", "PME", "Varejo", "Educacao"]
CIDADES = [
    ("Porto Alegre", "RS"),
    ("Sao Paulo", "SP"),
    ("Recife", "PE"),
    ("Brasilia", "DF"),
    ("Manaus", "AM"),
    ("Curitiba", "PR"),
    ("Belo Horizonte", "MG"),
    ("Salvador", "BA"),
]
NOMES = [
    "Ana Souza",
    "Bruno Lima",
    "Carla Dias",
    "Diego Alves",
    "Elena Prado",
    "Felipe Nunes",
    "Gabriela Reis",
    "Henrique Costa",
    "Iris Martins",
    "Joao Pereira",
    "Karina Lopes",
    "Lucas Mendes",
]


def _build_clientes(n_clientes: int = 80) -> pd.DataFrame:
    rows = []
    for i in range(1, n_clientes + 1):
        cidade, uf = CIDADES[i % len(CIDADES)]
        rows.append(
            {
                "cliente_id": i,
                "nome": NOMES[i % len(NOMES)] + f" {i}",
                "segmento": SEGMENTOS[i % len(SEGMENTOS)],
                "cidade": cidade,
                "uf": uf,
            }
        )
    return pd.DataFrame(rows)


def _build_vendas(rng: np.random.Generator, n: int, n_clientes: int) -> pd.DataFrame:
    prod_idx = rng.integers(0, len(PRODUTOS), n)
    qtd = rng.integers(1, 12, n)
    preco = np.round(rng.uniform(29.9, 6500.0, n), 2)
    desconto = np.round(rng.choice([0.0, 0.0, 5.0, 10.0, 15.0], n), 1)
    valor = np.round(qtd * preco * (1.0 - desconto / 100.0), 2)
    datas = pd.date_range("2024-01-01", periods=n, freq="h")
    return pd.DataFrame(
        {
            "venda_id": np.arange(1, n + 1),
            "cliente_id": rng.integers(1, n_clientes + 1, n),
            "produto": [PRODUTOS[i][0] for i in prod_idx],
            "categoria": [PRODUTOS[i][1] for i in prod_idx],
            "quantidade": qtd,
            "preco_unitario": preco,
            "desconto_pct": desconto,
            "valor_linha": valor,
            "data_venda": datas,
            "regiao": [REGIOES[i % len(REGIOES)] for i in range(n)],
            "canal": [CANAIS[i % len(CANAIS)] for i in range(n)],
            "status": [STATUS[i % len(STATUS)] for i in range(n)],
        }
    )


def main() -> None:
    DEMO_DIR.mkdir(exist_ok=True)
    rng = np.random.default_rng(42)
    n_clientes = 80
    n_vendas = 10_000

    clientes = _build_clientes(n_clientes)
    vendas = _build_vendas(rng, n_vendas, n_clientes)

    clientes.to_parquet(CLIENTES_OUT, index=False)
    vendas.to_parquet(VENDAS_OUT, index=False)

    print(
        f"Gerado {CLIENTES_OUT.name} ({len(clientes)} linhas, {CLIENTES_OUT.stat().st_size} bytes)"
    )
    print(f"Gerado {VENDAS_OUT.name} ({len(vendas)} linhas, {VENDAS_OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

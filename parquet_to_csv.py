#!/usr/bin/env python3
"""Converte todos os arquivos .parquet da pasta input/ para CSV em output/."""

from pathlib import Path

import pandas as pd


def main() -> None:
    base = Path(__file__).resolve().parent
    pasta_input = base / "input"
    pasta_output = base / "output"
    pasta_output.mkdir(exist_ok=True)

    parquets = sorted(pasta_input.glob("*.parquet"))

    if not parquets:
        print("Nenhum arquivo .parquet encontrado na pasta input/.")
        return

    for arquivo in parquets:
        destino = pasta_output / f"{arquivo.stem}.csv"
        print(f"Convertendo {arquivo.name} -> output/{destino.name} ...")
        df = pd.read_parquet(arquivo)
        df.to_csv(destino, index=False, encoding="utf-8-sig")
        print(f"  {len(df):,} linhas, {len(df.columns)} colunas")

    print(f"\nConcluído: {len(parquets)} arquivo(s) convertido(s).")


if __name__ == "__main__":
    main()

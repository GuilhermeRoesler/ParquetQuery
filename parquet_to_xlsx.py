#!/usr/bin/env python3
"""Converte todos os arquivos .parquet da pasta input/ para XLSX em output/."""

from pathlib import Path

import pandas as pd

LIMITE_LINHAS_EXCEL = 1_048_576


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
        destino = pasta_output / f"{arquivo.stem}.xlsx"
        print(f"Convertendo {arquivo.name} -> output/{destino.name} ...")
        df = pd.read_parquet(arquivo)

        if len(df) > LIMITE_LINHAS_EXCEL:
            print(
                f"  AVISO: {len(df):,} linhas excedem o limite do Excel "
                f"({LIMITE_LINHAS_EXCEL:,}). Apenas as primeiras "
                f"{LIMITE_LINHAS_EXCEL:,} serão exportadas."
            )
            df = df.head(LIMITE_LINHAS_EXCEL)

        df.to_excel(destino, index=False, engine="openpyxl")
        print(f"  {len(df):,} linhas, {len(df.columns)} colunas")

    print(f"\nConcluído: {len(parquets)} arquivo(s) convertido(s).")


if __name__ == "__main__":
    main()

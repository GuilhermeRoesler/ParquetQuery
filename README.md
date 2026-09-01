# Parquet Query

Aplicação **Streamlit** para explorar arquivos Parquet e CSV com **DuckDB**, SQL ad-hoc, colunas calculadas (DuckDB ou DAX) e exportação versionada.

## Início rápido

```bash
# Windows
run.bat

# Linux / macOS
./run.sh

# Com dependências de desenvolvimento (pytest, ruff)
./run.sh --dev
run.ps1 -Dev
```

Coloque arquivos `.parquet` ou `.csv` em `data/` e abra o app no navegador (porta padrão `8501`).

## Desenvolvimento

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/
python -m ruff check .
```

## Documentação

A especificação completa do projeto está em **[LIVING_SPEC.md](LIVING_SPEC.md)** — arquitetura, abas, session state, tradutores DAX/M e convenções de código.

---
name: architecture
description: >-
  Arquitetura Parquet Query (Streamlit + DuckDB): stack, fluxo de dados, SQL
  derivado, paginação, caches, mapa de edição e estado conhecido. Use ao alterar
  pq/, app.py, queries ou comportamento das abas.
---

# Arquitetura

## Stack

Streamlit + DuckDB · dados em `data/` · entrada `.parquet`/`.csv` · saída Parquet/CSV/XLSX.

- Licença: MIT (`LICENSE`)
- Dependências: `pyproject.toml` (fonte); `requirements.txt` / `requirements-dev.txt` espelham Cloud, launchers e build portátil
- Instalação local alternativa: `pip install -e ".[dev]"`
- Pacote: `pq/` (`db`, `ui`, `export`, `storage`, `translators`, `overview`)
- Entrada: `app.py`
- Ícone: `assets/icon.png` (+ `assets/icon.svg` fonte, `assets/icon.ico` instalador Windows); `page_icon` em `app.py`
- Launch: `run.bat` / `run.ps1` / `./run.sh` ou `streamlit run app.py` (detalhes → README)
- Porta: `scripts/find_free_port.py`

**Release portátil** (usuário leigo): tag `v*` → `.github/workflows/release.yml` → builds paralelos → GitHub Release.

| Artefato | Script | Runtime embutido |
|----------|--------|------------------|
| `ParquetQuery-{versão}-win64.zip` | `scripts/build_portable.ps1` | Python embeddable 3.11 (Windows) |
| `ParquetQuery-{versão}-win64-setup.exe` | `scripts/build_portable.ps1` + `installer/parquet-query.iss` (Inno Setup 6) | mesmo staging do ZIP |
| `ParquetQuery-{versão}-linux-{x64\|arm64}.tar.gz` | `scripts/build_portable.sh` | python-build-standalone 3.11 |
| `ParquetQuery-{versão}-macos-{x64\|arm64}.tar.gz` | `scripts/build_portable.sh` | python-build-standalone 3.11 |

Launchers: `Iniciar Parquet Query.bat` (Windows) / `iniciar-parquet-query.sh` (Unix). Pacote inclui deps + app + `assets/` + pasta `data/`.

**Instalador Windows:** monta sobre o staging do ZIP; instala em `%LOCALAPPDATA%\Programs\Parquet Query` (sem admin; `PrivilegesRequired=lowest`); atalho no menu Iniciar; CI baixa Inno Setup 6.7.3 e exige `-RequireInstaller`. Build local sem Inno: `-SkipInstaller` (só ZIP). Ícone: `assets/icon.ico`.

**Modo vitrine (Streamlit Community Cloud):** `pq/config.is_cloud_mode` — `PQ_CLOUD_MODE=1` (teste local), vars `STREAMLIT_SHARING` / `STREAMLIT_CLOUD`, ou repo em `/mount/src/`. Upload sidebar (até 50 MB); demo em `demo/` (`vendas_demo` + `clientes_demo`); auto-load dos exemplos na 1ª visita (`cloud_demo_autoload_done`); receitas SQL/DAX/M (`pq/ui/demo_recipes.py`); dir efêmero por sessão (`pq/storage/cloud.py`); export só por download — sem «Salvar em data/». Local inalterado.

## Fluxo de dados

Sidebar carrega arquivos → `register_view(stem, path)` cria view DuckDB. Aba **Colunas** empilha transformações em `derived_by_table`. Abas consultam via `work_from_clause(table, derived_sql)`. **Exportar** grava `{base}_vN.ext` e atualiza `_manifest.json`.

1. Arquivo em `data/` → view `"stem"` via `read_parquet` / `read_csv_auto`
2. Sem transformações: `FROM "stem"`
3. Com colunas calculadas: `FROM (derived_sql) __work__`
4. Export → `record_version` + `save_manifest`

Cada rerun: `init_state` → `get_connection` → `render_sidebar` → `build_work_context` → 4 abas com `WorkContext` compartilhado. Troca de tabela ou derived SQL reseta o editor (`sql_editor_ctx` em `pq/ui/app_context.py`).

## SQL derivado

Transformações **não** alteram o Parquet — acumulam SELECT em `st.session_state.derived_by_table[table]`.

| Onde | Função |
|------|--------|
| `pq/db/derived.py` | `work_from_clause`, `build_derived_select`, `working_sql`, `default_preview_sql` |
| `pq/ui/state.py` | `get_derived_sql` / `set_derived_sql` / `has_derived_sql` / `init_state` |
| `pq/db/sql_utils.py` | `validate_derived_sql` — executar **antes** de aplicar |

Aliases fixos: `__work__` (trabalho), `__validate__` (validação), `__q__` (paginação).

## Paginação

Dataset grande → **`paginate_sql`** (COUNT cacheado via `cached_sql_count` + LIMIT/OFFSET). Não materializar DataFrame inteiro. O mesmo COUNT alimenta o contador da sidebar (`working_sql`).

- Invalidar COUNT: `clear_sql_count_cache()` ao mudar derived SQL ou recarregar tabelas
- Preview Explorar: sob demanda (botão **Atualizar preview**)

## Caches Streamlit

| Cache | Uso |
|-------|-----|
| `@st.cache_resource` | `get_connection` |
| `@st.cache_data` (ttl 300s) | `get_schema`, `describe_sql_cached`, overview |

**Nunca** passar `DuckDBPyConnection` como argumento de `@st.cache_data` — chamar `get_connection()` no corpo.

Invalidação: `get_schema.clear()`, `invalidate_data_caches()` (overview, COUNT, describe, schemas do editor).

## Onde editar

| Tarefa | Onde |
|--------|------|
| Nova aba / UI | `pq/ui/tabs/` — manter `WorkContext`; state em `pq/ui/state.py` |
| Sidebar / carregar | `pq/ui/sidebar.py` |
| SQL derivado / preview | `pq/db/derived.py`; ler/gravar via `pq/ui/state.py` |
| Paginação | `pq/ui/components/pagination.py` (`paginate_sql`, `cached_sql_count`) |
| Erros / manifesto UI | `pq/ui/components/errors.py`, `pq/ui/components/manifest.py` |
| Export / save | `pq/export/query_export.py`, `pq/storage/data_store.py` |
| Modo cloud / demo | `pq/storage/cloud.py`, `pq/config.is_cloud_mode`, `demo/`, `pq/ui/demo_recipes.py`, auto-load em `pq/ui/sidebar.py` |
| Nova função DAX | `pq/translators/dax.py` → `_Parser._translate_call` |
| Novo passo M | `pq/translators/m.py` → `_translate_step` |
| Novo formato de arquivo | `pq/config.LOADABLE_EXTENSIONS`, `pq/db/connection.duckdb_read_expr`, `pq/export/io` |
| Overview / formatação pt-BR | `pq/overview/` |

## Estado conhecido

| Tópico | Status |
|--------|--------|
| App local single-user | Sem autenticação; pacotes portáteis (win/linux/macos) + setup.exe Windows via GitHub Releases |
| Demo online (Streamlit Cloud) | Auto-load de `demo/vendas_demo.parquet` + `clientes_demo.parquet`; receitas SQL/DAX/M; upload efêmero; sem persistência em disco |
| DAX / M | Subconjuntos — não paridade com Power BI |
| Legacy `input/`/`output/` | Migrados para `data/` na 1ª execução |
| Testes | pytest; CI: ruff (lint+format), pytest (3.10–3.12, cov≥45%), mypy, pip-audit; pre-commit local |

# Parquet Query — Spec

> **Última atualização:** 2026-09-01

Spec enxuto para IA e contribuidores. Guia de usuário, CI e detalhes de UI → **[README.md](README.md)**.

---

## Protocolo

1. Ler este arquivo no início de tarefas não triviais.
2. Ao alterar comportamento ou arquitetura: atualizar `Última atualização` e as seções afetadas **neste spec**.
3. Se a mudança for visível ao usuário (abas, fluxo, CLI, troubleshooting): atualizar também **[README.md](README.md)**.
4. Histórico no git — sem changelog nem versão aqui.
5. **Documentação e código devem refletir um ao outro** — se divergirem, corrija o doc ou o código na mesma sessão; nunca deixe inconsistente.

---

## Stack

Streamlit + DuckDB · dados em `data/` · entrada `.parquet`/`.csv` · saída Parquet/CSV/XLSX.

Executar: `run.bat` / `run.ps1` / `./run.sh` ou `streamlit run app.py`. Detalhes de launch → README.

Release Windows (usuário leigo): tag `v*` → workflow `.github/workflows/release.yml` → `scripts/build_portable.ps1` empacota Python embeddable 3.11 + deps + app em `dist/ParquetQuery-{versão}-win64.zip`; launcher `Iniciar Parquet Query.bat` na raiz do zip.

Pacote principal: `pq/` (`db`, `ui`, `export`, `storage`, `translators`). Entrada: `app.py`.

Shims legados na raiz (não duplicar lógica): `data_store.py`, `pq_dax_translator.py`, `pq_m_translator.py`.

---

## Fluxo de dados

Sidebar carrega arquivos → `register_view(stem, path)` cria view DuckDB. Aba **Colunas** empilha transformações em `derived_by_table`. Abas consultam via `work_from(table)`. **Exportar** grava `{base}_vN.ext` e atualiza `_manifest.json`.

1. Arquivo em `data/` → view `"stem"` via `read_parquet` / `read_csv_auto`
2. Sem transformações: `FROM "stem"`
3. Com colunas calculadas: `FROM (derived_sql) __work__`
4. Export → `record_version` + `save_manifest`

Cada rerun Streamlit: `init_state` → `get_connection` → `render_sidebar` → `build_work_context` → 4 abas com `WorkContext` compartilhado. Troca de tabela ou derived SQL reseta o editor (`sql_editor_ctx` em `pq/ui/app_context.py`).

---

## Decisões técnicas

### SQL derivado

Transformações **não** alteram o Parquet — acumulam SELECT em `st.session_state.derived_by_table[table]`.

| Onde | Função |
|------|--------|
| `pq/db/derived.py` | `work_from_clause`, `build_derived_select`, `working_sql` |
| `pq/ui/state.py` | Wrappers (`work_from`, `set_derived_sql`, …) + session state |
| `pq/db/sql_utils.py` | `validate_derived_sql` — executar **antes** de aplicar |

Aliases fixos: `__work__` (base de trabalho), `__validate__` (validação), `__q__` (paginação).

### Paginação

Dataset grande → **`paginate_sql`** (COUNT cacheado em session state + LIMIT/OFFSET no DuckDB).

DataFrame pequeno já em RAM → `paginate`. Invalidar COUNT: `clear_sql_count_cache()` ao mudar derived SQL ou recarregar tabelas.

### Caches Streamlit

`get_connection` → `@st.cache_resource`. Schema e overview → `@st.cache_data` (ttl 300s).

**Nunca** passar `DuckDBPyConnection` como argumento de `@st.cache_data` — usar `get_connection()` no corpo.

Invalidação: `get_schema.clear()`, `clear_overview_cache()`, `clear_sql_count_cache()`.

### Export

`pq/export/query_export.py`: Parquet/CSV via DuckDB `COPY`; XLSX em chunks (`fetch_df_chunk`, 10k linhas).

Limite XLSX: `LIMITE_XLSX = 1_048_576`. Destinos via `safe_data_path` (anti-traversal).

### Versionamento (`data/`)

| Conceito | Regra |
|----------|-------|
| Original | `{base}.parquet` → versão lógica `0` |
| Exportações | `{base}_v1`, `{base}_v2`, … |
| Metadados | `data/_manifest.json` (`bases → versions → file, format, …`) |

Manifest corrompido: `load_manifest` retorna fallback + aviso na UI; `save_manifest` limpa flags `_corrupt`.

Funções: `pq/storage/data_store.py` — `base_name_from`, `record_version`, `build_timeline`, `migrate_legacy_dirs`.

### Session state (chaves principais)

`loaded_tables`, `derived_by_table`, `last_result_sql`, `sql_editor` / `sql_editor_ctx`, `sql_last_submit_id`, `pg_{key}`, `sql_cnt_*`.

Definido em `pq/ui/state.py`; `init_state()` só inicializa defaults — `active_table` vem da sidebar.

### Tradutores

- **DAX** (`pq/translators/dax.py`): parcial; `'Tabela'[Col]` → `"Col"`; identificador desconhecido → `ParseError`. Funções suportadas: ver `_Parser._translate_call`.
- **M** (`pq/translators/m.py`): passos `Table.SelectRows`, `TransformColumnTypes`, `RemoveColumns`, `SelectColumns`; parâmetros via CTE `params`. Sem joins/pivots.

Erros compartilhados: `ParseError` em `pq/translators/errors.py`.

---

## Onde editar

| Tarefa | Onde |
|--------|------|
| Nova aba / UI | `pq/ui/tabs/` — manter `WorkContext`, helpers de `pq/ui/state.py` |
| Sidebar / carregar arquivos | `pq/ui/sidebar.py` |
| SQL derivado / preview | `pq/db/derived.py`, `pq/ui/state.py` |
| Paginação | `pq/ui/components/pagination.py` |
| Export / save | `pq/export/query_export.py`, `pq/storage/data_store.py` |
| Nova função DAX | `pq/translators/dax.py` → `_Parser._translate_call` |
| Novo passo M | `pq/translators/m.py` → `_translate_step` |
| Novo formato de arquivo | `pq/config.LOADABLE_EXTENSIONS`, `pq/db/connection.duckdb_read_expr`, `pq/export/io` |
| Overview / formatação pt-BR | `pq/overview/` |

Após mudanças: atualizar este spec (e README se user-facing); `python -m pytest tests/ -q`, `python -m ruff check .`, `python -m ruff format --check .`, `python -m mypy pq`.

---

## Convenções

- `from __future__ import annotations`; paths com `pathlib.Path`
- Identificadores SQL: `quote_ident()`; SQL final: `strip_sql()` (remove `;` trailing)
- UI em português; type hints; diff mínimo; sem refatoração não solicitada
- Lint: ruff (E, F, I, UP, B, SIM, RUF), linha máx. 100; formato via `ruff format`

---

## Estado conhecido

| Tópico | Status |
|--------|--------|
| App local single-user | Sem autenticação; distribuição Windows via zip portátil (GitHub Releases) |
| DAX / M | Subconjuntos — não paridade com Power BI |
| Legacy `input/`/`output/` | Migrados para `data/` na 1ª execução |
| Testes | 49 pytest; CI: ruff (lint+format), pytest (3.9–3.12, cov≥45%), mypy, pip-audit; pre-commit local |

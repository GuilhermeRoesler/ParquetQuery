---
name: ui-streamlit
description: >-
  Padrões da UI Streamlit do Parquet Query: session state, WorkContext, sidebar,
  abas e componentes. Use ao editar pq/ui/ ou o fluxo de rerun do app.
---

# UI Streamlit

## Ciclo de rerun

`init_state` → `get_connection` → `render_sidebar` → `build_work_context` → abas com `WorkContext` compartilhado.

Troca de tabela ou derived SQL reseta o editor (`sql_editor_ctx` em `pq/ui/app_context.py`).

## Session state (chaves principais)

Definido em `pq/ui/state.py`. `init_state()` só inicializa defaults — `active_table` vem da sidebar.

| Chave | Papel |
|-------|--------|
| `loaded_tables` | Tabelas carregadas |
| `derived_by_table` | SQL derivado por tabela |
| `last_result_sql` | Último SELECT da aba SQL |
| `sql_editor` / `sql_editor_ctx` | Editor e contexto |
| `sql_last_submit_id` | Submit do editor |
| `pg_{key}` | Paginação |
| `sql_cnt_*` | COUNT cacheado |
| `preview_ready_token` | Preview sob demanda |
| `sql_table_schemas` | Schemas do autocomplete |
| `dax_translate_cache` | Cache de tradução DAX |

API derived: `get_derived_sql` / `set_derived_sql` / `has_derived_sql`.

## Onde editar

| Peça | Arquivo |
|------|---------|
| Sidebar / carregar | `pq/ui/sidebar.py` (cloud: auto-load demo) |
| Receitas demo | `pq/ui/demo_recipes.py` |
| Estado | `pq/ui/state.py` |
| Contexto compartilhado | `pq/ui/app_context.py` |
| Abas | `pq/ui/tabs/` — manter `WorkContext` |
| Paginação | `pq/ui/components/pagination.py` (`paginate_sql`, `cached_sql_count`) |
| Erros | `pq/ui/components/errors.py` |
| Manifesto UI | `pq/ui/components/manifest.py` |

## Regras de UI

- Textos da interface em português
- Preview Explorar: só após **Atualizar preview** (não query a cada rerun)
- Dados grandes: nunca carregar resultado completo em DataFrame para paginar — usar `paginate_sql`
- Após mudar derived SQL: invalidar COUNT (`clear_sql_count_cache`) e caches de schema/describe conforme o fluxo existente

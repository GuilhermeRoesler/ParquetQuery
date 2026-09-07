---
name: translators
description: >-
  Tradutores DAX e Power Query (M) para SQL DuckDB no Parquet Query. Use ao
  adicionar funções DAX, passos M, ou corrigir ParseError em pq/translators/.
---

# Tradutores DAX / M

Erros compartilhados: `ParseError` em `pq/translators/errors.py`.

São **subconjuntos** — sem paridade com Power BI.

## DAX (`pq/translators/dax.py`)

- Parcial: `'Tabela'[Col]` → `"Col"`
- Identificador desconhecido → `ParseError`
- Funções suportadas: ver `_Parser._translate_call`
- Cache de UI: `dax_translate_cache` no session state

**Nova função DAX:** estender `_Parser._translate_call` + testes em `tests/`.

## M / Power Query (`pq/translators/m.py`)

Passos suportados:

- `Table.SelectRows`
- `TransformColumnTypes`
- `RemoveColumns`
- `SelectColumns`

Parâmetros via CTE `params`. Sem joins/pivots.

**Novo passo M:** estender `_translate_step` + testes.

## Ao alterar

1. Manter mensagens de erro claras (UI em português quando expostas)
2. Cobrir com pytest (`tests/test_*translator*` ou equivalente)
3. Atualizar esta skill (e `architecture` se o mapa de edição mudar); README se a superfície user-facing mudar
4. Não prometer paridade Power BI no README/UI

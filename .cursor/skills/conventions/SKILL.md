---
name: conventions
description: >-
  Convenções de código do Parquet Query: pathlib, SQL helpers, UI em português,
  ruff, mypy e diff mínimo. Use ao escrever ou revisar Python no repositório.
---

# Convenções

## Código

- `from __future__ import annotations`
- Paths com `pathlib.Path`
- Identificadores SQL: `quote_ident()`; SQL final: `strip_sql()` (remove `;` trailing)
- UI (labels, mensagens, erros): **português**
- Type hints; diff mínimo; sem refatoração não solicitada

## Lint e tipagem

- Ruff: regras E, F, I, UP, B, SIM, RUF; linha máx. **100**; formato via `ruff format`
- Mypy no núcleo (`storage`, `export`, `db` exceto UI); `pq/ui/` e `pq/translators/` excluídos/ignorados conforme `pyproject.toml`

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy pq --config-file pyproject.toml
python -m pytest tests/ -q
```

## Escopo de mudanças

- Só o necessário para a tarefa
- Não criar docs markdown extras a menos que pedidos
- Não “melhorar” código adjacente não relacionado
- Preferir editar arquivos existentes a criar abstrações novas
- Após mudança técnica: atualizar a skill correspondente (ver `living-spec`); README se user-facing

## Comunicação com o usuário

Respostas do agente em **português**, diretas e concisas.

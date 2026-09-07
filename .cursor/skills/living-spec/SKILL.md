---
name: living-spec
description: >-
  Protocolo de documentação do Parquet Query: skills em .cursor/skills/ são a
  fonte canônica de decisões técnicas; README para fluxo do usuário. Use no
  início de tarefas não triviais e ao concluir mudanças de comportamento.
---

# Especificação viva (skills)

## Fonte canônica

| Onde | Conteúdo | Quando atualizar |
|------|----------|------------------|
| `.cursor/skills/*/SKILL.md` | Decisões técnicas, arquitetura, convenções, mapa de edição | Mudança interna / arquitetura / comportamento |
| `README.md` | Uso, abas, launch, cloud, troubleshooting | Mudança visível ao usuário ou setup |

Rules em `.cursor/rules/` são só ponteiros breves para estas skills. Histórico no git — sem changelog nas skills.

## Protocolo

1. **Início** — ler a skill relevante (e `architecture` se o fluxo de dados estiver em jogo) antes de implementar ou explicar algo não trivial.
2. **Durante** — se skill e código divergirem, corrigir um dos dois na mesma sessão; nunca deixar inconsistente.
3. **Fim** — se alterou comportamento ou arquitetura:
   - atualizar a(s) skill(s) afetada(s)
   - se user-facing (abas, fluxo, CLI, troubleshooting): atualizar também `README.md`

## Índice de skills

| Skill | Assunto |
|-------|---------|
| `architecture` | Stack, fluxo, derived SQL, paginação, caches, mapa de edição, estado conhecido |
| `conventions` | Estilo, lint, tipagem, diff |
| `ui-streamlit` | Session state, WorkContext, abas |
| `export-storage` | Export, `data/`, manifest, cloud |
| `translators` | DAX e M → SQL |

## Após mudanças de código

```bash
python -m pytest tests/ -q
python -m ruff check .
python -m ruff format --check .
python -m mypy pq
```

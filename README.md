# Parquet Query

Aplicação **Streamlit** para explorar arquivos **Parquet** e **CSV** com **DuckDB** — SQL ad-hoc, colunas calculadas (DuckDB ou DAX do Power BI), tradutor Power Query (M) e exportação versionada em `data/`.

**Requisitos:** Python 3.9+ · Windows, Linux ou macOS

---

## Início rápido

1. Coloque arquivos `.parquet` ou `.csv` na pasta `data/`.
2. Inicie o app:

```bash
# Windows
run.bat          # ou: run.ps1

# Linux / macOS
./run.sh
```

3. Abra o navegador em `http://127.0.0.1:8501` (porta alternativa se 8501 estiver ocupada).

Os scripts de launch criam/ativam `.venv`, instalam dependências, garantem `data/` e sobem o Streamlit. Flag `--dev` / `-Dev` instala pytest e ruff.

---

## Uso do app

1. **Carregar** — sidebar: marque arquivos e clique **Carregar selecionados**
2. **Explorar** — schema, preview (100 linhas), overview classificatório ou numérico
3. **SQL** — editor DuckDB; **Ctrl+Enter** ou Executar; tradutor M no expander
4. **Colunas** — colunas calculadas (SQL ou DAX), renomear, remover, TRY_CAST
5. **Exportar** — download ou salvar em `data/` como nova versão (`{base}_vN`) ou sobrescrever

Versões exportadas: `vendas_v1.parquet`, `vendas_v2.parquet`, … O original fica como `vendas.parquet` (sem sufixo).

---

## O que o app faz

| Recurso | Descrição |
|---------|-----------|
| **Explorar** | Schema, preview paginado e overview de valores (classificatório ou numérico) |
| **SQL** | Editor com autocomplete; execução paginada server-side; tradutor M → SQL |
| **Colunas** | Colunas calculadas (SQL ou DAX), renomear, remover, TRY_CAST |
| **Exportar** | Download ou salvar em `data/` com versionamento `{base}_vN` e timeline |

Dados grandes são processados no DuckDB — paginação e export Parquet/CSV via `COPY`, sem carregar o dataset inteiro na RAM.

---

## Desenvolvimento

```bash
./run.sh --dev          # Linux/macOS
run.ps1 -Dev            # Windows

# Ou manualmente
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt -r requirements-dev.txt

python -m pytest tests/ -q
python -m ruff check .
```

CI (GitHub Actions): `ruff check` + `pytest` em push/PR para `main`/`master`.

**Documentação:** ao mudar código, atualize `LIVING_SPEC.md` (decisões técnicas) e `README.md` (se user-facing) na mesma sessão — doc e código devem refletir um ao outro.

---

## Estrutura do projeto

```
app.py              # Entrada Streamlit
pq/                 # Pacote principal
  db/               # DuckDB — conexão, schema, derived, paginação
  ui/               # Streamlit — sidebar, abas, componentes
  export/           # COPY/streaming, io
  storage/          # Versionamento + _manifest.json
  translators/      # DAX e M → SQL
  overview/         # SQL de overview, formatação pt-BR
data/               # Arquivos + _manifest.json
tests/              # pytest (29 testes)
LIVING_SPEC.md      # Decisões técnicas para IA/contribuidores
```

Shims na raiz: `data_store.py`, `pq_dax_translator.py`, `pq_m_translator.py`.

---

## Solução de problemas

| Sintoma | Ação |
|---------|------|
| Porta 8501 ocupada | Scripts tentam 8502+; ou `STREAMLIT_SERVER_PORT` |
| Exportar «Último resultado» vazio | Execute um SELECT na aba SQL primeiro |
| XLSX truncado (>1M linhas) | Use Parquet ou CSV |
| DAX «função não suportada» | Reescreva em SQL DuckDB na aba Colunas |
| Arquivo exportado não aparece | Marque na sidebar e **Carregar** |
| `_manifest.json` corrompido | Sidebar avisa; próximo save recria metadados |

---

## Documentação

| Arquivo | Conteúdo | Quando atualizar |
|---------|----------|------------------|
| **[LIVING_SPEC.md](LIVING_SPEC.md)** | Decisões técnicas, armadilhas, mapa de edição | Mudança de arquitetura, convenções ou comportamento interno |
| **README.md** (este) | Uso, dev, troubleshooting | Mudança visível ao usuário ou ao fluxo de setup |

Detalhes de tradutores DAX/M: código em `pq/translators/`. Doc e código devem estar sempre alinhados.

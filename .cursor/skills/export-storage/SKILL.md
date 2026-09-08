---
name: export-storage
description: >-
  Exportação DuckDB e versionamento em data/ do Parquet Query: COPY, XLSX em
  chunks, _manifest.json, safe paths e modo cloud. Use ao editar pq/export/ ou
  pq/storage/.
---

# Export e storage

## Export (`pq/export/`)

`query_export.py`:

- Parquet/CSV via DuckDB `COPY`
- XLSX em chunks (`fetch_df_chunk`, 10k linhas)
- Após COPY, `row_count` vem do arquivo gerado (não reexecuta a query)
- Extensão: `pq/export/io.export_extension`
- Limite XLSX: `LIMITE_XLSX = 1_048_576`
- Destinos: `safe_data_path` (anti-traversal)

## Versionamento (`data/`)

| Conceito | Regra |
|----------|-------|
| Original | `{base}.parquet` → versão lógica `0` |
| Exportações | `{base}_v1`, `{base}_v2`, … |
| Metadados | `data/_manifest.json` (`bases → versions → file, format, …`) |

Funções em `pq/storage/data_store.py`:

- `base_name_from`, `record_version`, `build_timeline` (um scan de `data/`)
- `migrate_legacy_dirs` (legacy `input/`/`output/` → `data/` na 1ª execução)

Manifest corrompido: `load_manifest` retorna fallback + aviso na UI; `save_manifest` limpa flags `_corrupt`.

## Modo cloud

- Detecção: `PQ_CLOUD_MODE=1`, vars Streamlit Cloud, ou `/mount/src/` (`pq/config.is_cloud_mode`)
- Upload sidebar (até 50 MB); demo em `demo/` (`vendas_demo` ~10k linhas + `clientes_demo` para JOIN)
- Auto-load dos exemplos na primeira visita da sessão (`cloud_demo_autoload_done` em `pq/ui/sidebar.py`)
- Rótulos amigáveis via `demo_source_label`; receitas em `pq/ui/demo_recipes.py`
- Diretório efêmero por sessão (`pq/storage/cloud.py`)
- Export só por download — sem «Salvar em data/»
- Instalação local inalterada — upload na sidebar grava em `data/` (até 500 MB; `LOCAL_UPLOAD_MAX_BYTES` / `maxUploadSize`); botão **Abrir pasta data/** via `open_in_file_manager`
- Helpers compartilhados: `sanitize_upload_stem`, `save_uploaded_file`, `process_sidebar_uploads` (keys distintos local/cloud)
- Regenerar datasets: `python scripts/gen_demo_parquet.py`

## Checklist ao mudar export/storage

- [ ] Paths só via helpers seguros (`safe_data_path` / equivalentes)
- [ ] Versionamento `{base}_vN` preservado
- [ ] Manifest atualizado via `record_version` / `save_manifest`
- [ ] Cloud: sem persistência permanente em disco
- [ ] Atualizar skill(s) afetada(s) (e README se user-facing)

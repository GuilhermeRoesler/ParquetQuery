#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo
echo " Parquet Query"
echo " ============="
echo

if [[ ! -f app.py ]]; then
    echo "[ERRO] app.py não encontrado. Execute este script na raiz do projeto." >&2
    exit 1
fi

if [[ ! -f requirements.txt ]]; then
    echo "[ERRO] requirements.txt não encontrado." >&2
    exit 1
fi

if command -v python3 >/dev/null 2>&1; then
    PY=python3
elif command -v python >/dev/null 2>&1; then
    PY=python
else
    echo "[ERRO] Python 3 não encontrado." >&2
    echo "       Instale Python 3.9+ e tente novamente." >&2
    exit 1
fi

if ! "$PY" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo "[ERRO] Python 3.9 ou superior é necessário." >&2
    "$PY" --version >&2 || true
    exit 1
fi

echo "Python: $("$PY" --version)"

if [[ ! -x .venv/bin/python ]]; then
    echo
    echo "Criando ambiente virtual em .venv ..."
    "$PY" -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate

echo
echo "Instalando dependências ..."
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q

mkdir -p data

REQUESTED_PORT="${STREAMLIT_SERVER_PORT:-8501}"
STREAMLIT_SERVER_PORT="$(python find_free_port.py "$REQUESTED_PORT")"

echo
if [[ "$STREAMLIT_SERVER_PORT" != "$REQUESTED_PORT" ]]; then
    echo "Porta ${REQUESTED_PORT} em uso; usando ${STREAMLIT_SERVER_PORT}."
    echo
fi
echo "Abrindo em http://localhost:${STREAMLIT_SERVER_PORT}"
echo "Pressione Ctrl+C para encerrar."
echo

exec python -m streamlit run app.py --server.headless true --server.port "$STREAMLIT_SERVER_PORT"

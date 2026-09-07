#!/usr/bin/env bash
# Monta pacote portátil Linux/macOS (Python relocatable + dependências + app).
set -euo pipefail

VERSION=""
TARGET=""
OUTPUT_DIR="dist"
REPO_URL=""
PYTHON_VERSION="3.11.16"
STANDALONE_TAG="20260901"

usage() {
  cat <<'EOF'
Uso: ./scripts/build_portable.sh --version X.Y.Z [opções]

Opções:
  --version X.Y.Z          Versão do release (obrigatório)
  --target NOME            linux-x64 | linux-arm64 | macos-x64 | macos-arm64
                           (padrão: detecta o host)
  --output-dir DIR         Pasta de saída relativa à raiz (padrão: dist)
  --repo-url URL           URL do repositório no LEIA-ME
  --python-version X.Y.Z   CPython no python-build-standalone (padrão: 3.11.16)
  --standalone-tag TAG     Tag do release astral-sh/python-build-standalone
  -h, --help               Mostra esta ajuda
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2:-}"
      shift 2
      ;;
    --target)
      TARGET="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --repo-url)
      REPO_URL="${2:-}"
      shift 2
      ;;
    --python-version)
      PYTHON_VERSION="${2:-}"
      shift 2
      ;;
    --standalone-tag)
      STANDALONE_TAG="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERRO] Argumento desconhecido: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ -z "$VERSION" ]]; then
  echo "[ERRO] --version é obrigatório." >&2
  usage >&2
  exit 1
fi

detect_target() {
  local os arch
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch="$(uname -m)"
  case "$os" in
    linux)
      case "$arch" in
        x86_64|amd64) echo "linux-x64" ;;
        aarch64|arm64) echo "linux-arm64" ;;
        *)
          echo "[ERRO] Arquitetura Linux não suportada: $arch" >&2
          return 1
          ;;
      esac
      ;;
    darwin)
      case "$arch" in
        x86_64) echo "macos-x64" ;;
        arm64) echo "macos-arm64" ;;
        *)
          echo "[ERRO] Arquitetura macOS não suportada: $arch" >&2
          return 1
          ;;
      esac
      ;;
    *)
      echo "[ERRO] SO não suportado por este script: $os (use build_portable.ps1 no Windows)." >&2
      return 1
      ;;
  esac
}

if [[ -z "$TARGET" ]]; then
  TARGET="$(detect_target)"
fi

case "$TARGET" in
  linux-x64)
    PLATFORM_LABEL="Linux x86_64"
    TRIPLE="x86_64-unknown-linux-gnu"
    ;;
  linux-arm64)
    PLATFORM_LABEL="Linux ARM64"
    TRIPLE="aarch64-unknown-linux-gnu"
    ;;
  macos-x64)
    PLATFORM_LABEL="macOS Intel (x86_64)"
    TRIPLE="x86_64-apple-darwin"
    ;;
  macos-arm64)
    PLATFORM_LABEL="macOS Apple Silicon (ARM64)"
    TRIPLE="aarch64-apple-darwin"
    ;;
  *)
    echo "[ERRO] --target inválido: $TARGET" >&2
    echo "       Use: linux-x64 | linux-arm64 | macos-x64 | macos-arm64" >&2
    exit 1
    ;;
esac

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_ROOT="$ROOT/$OUTPUT_DIR"
BUNDLE_NAME="ParquetQuery-${VERSION}-${TARGET}"
STAGING="$DIST_ROOT/$BUNDLE_NAME"
PYTHON_DIR="$STAGING/python"
ASSET="cpython-${PYTHON_VERSION}+${STANDALONE_TAG}-${TRIPLE}-install_only_stripped.tar.gz"
ASSET_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${STANDALONE_TAG}/${ASSET}"

step() {
  echo
  echo ">> $*"
}

step "Preparando staging em $STAGING"
rm -rf "$STAGING"
mkdir -p "$STAGING/data" "$DIST_ROOT"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

step "Baixando Python relocatable ${PYTHON_VERSION} (${TARGET})"
ARCHIVE="$TMP_DIR/$ASSET"
if command -v curl >/dev/null 2>&1; then
  curl -fsSL "$ASSET_URL" -o "$ARCHIVE"
elif command -v wget >/dev/null 2>&1; then
  wget -q "$ASSET_URL" -O "$ARCHIVE"
else
  echo "[ERRO] curl ou wget é necessário para baixar o Python." >&2
  exit 1
fi

tar -xzf "$ARCHIVE" -C "$STAGING"
if [[ ! -x "$PYTHON_DIR/bin/python3" ]]; then
  echo "[ERRO] python3 não encontrado em $PYTHON_DIR/bin após extrair o archive." >&2
  exit 1
fi

PY="$PYTHON_DIR/bin/python3"

step "Garantindo pip"
"$PY" -m ensurepip --upgrade >/dev/null
"$PY" -m pip install --upgrade pip --no-warn-script-location -q

step "Instalando dependências do app"
REQUIREMENTS="$ROOT/requirements.txt"
if [[ ! -f "$REQUIREMENTS" ]]; then
  echo "[ERRO] Arquivo obrigatório ausente: requirements.txt" >&2
  exit 1
fi
"$PY" -m pip install -r "$REQUIREMENTS" --no-warn-script-location -q

step "Copiando arquivos do app"
for item in app.py LICENSE; do
  src="$ROOT/$item"
  if [[ ! -e "$src" ]]; then
    echo "[ERRO] Arquivo obrigatório ausente: $item" >&2
    exit 1
  fi
  cp "$src" "$STAGING/$item"
done
for item in pq assets; do
  src="$ROOT/$item"
  if [[ ! -e "$src" ]]; then
    echo "[ERRO] Arquivo obrigatório ausente: $item" >&2
    exit 1
  fi
  # rsync evita __pycache__ / .pyc do ambiente de desenvolvimento
  if command -v rsync >/dev/null 2>&1; then
    mkdir -p "$STAGING/$item"
    rsync -a --exclude '__pycache__' --exclude '*.pyc' "$src/" "$STAGING/$item/"
  else
    cp -R "$src" "$STAGING/$item"
    find "$STAGING/$item" -type d -name '__pycache__' -prune -exec rm -rf {} +
    find "$STAGING/$item" -type f -name '*.pyc' -delete
  fi
done

mkdir -p "$STAGING/scripts"
FIND_PORT_SRC="$ROOT/scripts/find_free_port.py"
if [[ ! -f "$FIND_PORT_SRC" ]]; then
  echo "[ERRO] Arquivo obrigatório ausente: scripts/find_free_port.py" >&2
  exit 1
fi
cp "$FIND_PORT_SRC" "$STAGING/scripts/find_free_port.py"

step "Gerando launcher e LEIA-ME"
cat > "$STAGING/iniciar-parquet-query.sh" <<'LAUNCHER'
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON="$ROOT/python/bin/python3"
if [[ ! -x "$PYTHON" ]]; then
  echo "[ERRO] Python embutido não encontrado. Reinstale o pacote." >&2
  exit 1
fi

mkdir -p "$ROOT/data"

echo
echo " Parquet Query"
echo " ============="
echo

PORT="$("$PYTHON" "$ROOT/scripts/find_free_port.py" 8501 | tr -d '[:space:]')"
if [[ -z "$PORT" ]]; then
  echo "[ERRO] Nenhuma porta livre a partir de 8501." >&2
  exit 1
fi

URL="http://localhost:${PORT}"
echo "Abrindo ${URL} ..."
echo "Pressione Ctrl+C para encerrar."
echo

open_browser() {
  case "$(uname -s)" in
    Darwin)
      open "$URL" >/dev/null 2>&1 || true
      ;;
    *)
      if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$URL" >/dev/null 2>&1 || true
      fi
      ;;
  esac
}

open_browser

exec "$PYTHON" -m streamlit run "$ROOT/app.py" \
  --server.headless true \
  --server.port "$PORT" \
  --browser.gatherUsageStats false
LAUNCHER
chmod +x "$STAGING/iniciar-parquet-query.sh"

if [[ -n "$REPO_URL" ]]; then
  REPO_LINE="Projeto: $REPO_URL"
else
  REPO_LINE="Projeto: consulte o repositório no GitHub."
fi

cat > "$STAGING/LEIA-ME.txt" <<EOF
Parquet Query v${VERSION} — ${PLATFORM_LABEL}
=========================================

INICIO RAPIDO
1. Extraia este arquivo (tar.gz) em uma pasta permanente
2. Coloque seus arquivos .parquet ou .csv na pasta data/
3. Execute: ./iniciar-parquet-query.sh
4. O navegador abrirá automaticamente (quando possível)

REQUISITOS
- ${PLATFORM_LABEL}
- Não é necessário instalar Python
- Linux: distribuição recente com glibc (Ubuntu 20.04+, Debian 11+, Fedora, etc.)

ENCERRAR
- Pressione Ctrl+C no terminal

PERMISSAO DE EXECUCAO
- Se necessário: chmod +x iniciar-parquet-query.sh

${REPO_LINE}
EOF

step "Criando arquivo tar.gz"
ARCHIVE_OUT="$DIST_ROOT/${BUNDLE_NAME}.tar.gz"
rm -f "$ARCHIVE_OUT"
tar -czf "$ARCHIVE_OUT" -C "$DIST_ROOT" "$BUNDLE_NAME"

echo
echo "Pacote criado: $ARCHIVE_OUT"
echo "Pasta staging: $STAGING"

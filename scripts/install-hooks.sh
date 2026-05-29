#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_DIR="$ROOT_DIR/.git/hooks"

if [[ ! -d "$HOOK_DIR" ]]; then
  echo "No existe .git/hooks. Inicializa Git primero."
  exit 1
fi

cat > "$HOOK_DIR/pre-commit" <<'EOF_HOOK'
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(git rev-parse --show-toplevel)"
"$ROOT_DIR/scripts/verify.sh"
EOF_HOOK

chmod +x "$HOOK_DIR/pre-commit"

echo "Hook instalado: pre-commit ejecutara scripts/verify.sh antes de cada commit."

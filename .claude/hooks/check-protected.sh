#!/usr/bin/env bash
# Bloquea modificaciones a archivos listados en .claude/protected.txt
# Usa $CLAUDE_PROJECT_DIR para resolver rutas desde la raíz del proyecto.

set -euo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
PROTECTED_FILE="$CLAUDE_PROJECT_DIR/.claude/protected.txt"
[ -f "$PROTECTED_FILE" ] || exit 0

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    tool_input = data.get('tool_input', {})
    print(tool_input.get('file_path', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")

[ -z "$FILE_PATH" ] && exit 0

REL_PATH="${FILE_PATH#$ROOT/}"

while IFS= read -r pattern; do
    [[ "$pattern" =~ ^#.*$ || -z "$pattern" ]] && continue
    if [[ "$REL_PATH" == $pattern || "$FILE_PATH" == $pattern ]]; then
        echo "🛑 BLOQUEADO: '$REL_PATH' está protegido por .claude/protected.txt (patrón: '$pattern')." >&2
        echo "Si necesitas tocar este archivo, pide permiso explícito al usuario." >&2
        exit 2
    fi
done < "$PROTECTED_FILE"

exit 0

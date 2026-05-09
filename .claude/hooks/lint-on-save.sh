#!/usr/bin/env bash
# Corre el linter/formatter apropiado al archivo modificado.
# No falla la ejecución de Claude; solo reporta.

set -uo pipefail

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
[ -f "$FILE_PATH" ] || exit 0

EXT="${FILE_PATH##*.}"

case "$EXT" in
    py)
        if command -v ruff &>/dev/null; then
            ruff format "$FILE_PATH" 2>/dev/null || true
            ruff check --fix "$FILE_PATH" 2>/dev/null || true
        fi
        ;;
    ts|tsx|js|jsx)
        if command -v biome &>/dev/null; then
            biome format --write "$FILE_PATH" 2>/dev/null || true
        elif command -v prettier &>/dev/null; then
            prettier --write "$FILE_PATH" 2>/dev/null || true
        fi
        ;;
esac

exit 0

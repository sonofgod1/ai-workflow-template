#!/usr/bin/env bash
# Bloquea modificaciones a archivos listados en .claude/protected.txt
# Lee el JSON del hook desde stdin, busca el path del archivo afectado.

set -euo pipefail

PROTECTED_FILE=".claude/protected.txt"
[ -f "$PROTECTED_FILE" ] || exit 0

# Claude Code pasa el contexto del tool call por stdin como JSON
INPUT=$(cat)

# Extraer el file_path del tool input (funciona para Write, Edit, MultiEdit)
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

# Normalizar a path relativo
REL_PATH="${FILE_PATH#$PWD/}"

# Comparar contra patrones de protected.txt
while IFS= read -r pattern; do
    # Saltar comentarios y líneas vacías
    [[ "$pattern" =~ ^#.*$ || -z "$pattern" ]] && continue

    # Match con globbing
    if [[ "$REL_PATH" == $pattern || "$FILE_PATH" == $pattern ]]; then
        echo "🛑 BLOQUEADO: '$REL_PATH' está protegido por .claude/protected.txt (patrón: '$pattern')." >&2
        echo "Si necesitas tocar este archivo, pide permiso explícito al usuario." >&2
        exit 2  # exit code 2 = bloquear el tool call en Claude Code
    fi
done < "$PROTECTED_FILE"

exit 0

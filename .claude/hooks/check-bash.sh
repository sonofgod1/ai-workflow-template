#!/usr/bin/env bash
# Bloquea comandos peligrosos sin confirmación explícita.
# Funciona correctamente desde cualquier subdirectorio del proyecto.

set -euo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    tool_input = data.get('tool_input', {})
    print(tool_input.get('command', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")

[ -z "$COMMAND" ] && exit 0

DANGEROUS_PATTERNS=(
    'rm[[:space:]]+-rf?[[:space:]]+/'
    'rm[[:space:]]+-rf?[[:space:]]+\*'
    'rm[[:space:]]+-rf?[[:space:]]+~'
    'git[[:space:]]+push.*--force'
    'git[[:space:]]+push.*-f([[:space:]]|$)'
    'git[[:space:]]+reset[[:space:]]+--hard'
    'git[[:space:]]+clean[[:space:]]+-fd'
    'DROP[[:space:]]+TABLE'
    'DROP[[:space:]]+DATABASE'
    'TRUNCATE'
    'mkfs\.'
    'dd[[:space:]]+if=.*of=/dev'
    ':(){.*};:'
    '>/dev/sda'
    'chmod[[:space:]]+-R[[:space:]]+777'
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
    if [[ "$COMMAND" =~ $pattern ]]; then
        echo "🛑 COMANDO PELIGROSO DETECTADO: $COMMAND" >&2
        echo "Patrón: $pattern" >&2
        echo "Si realmente quieres ejecutar esto, pide al usuario que escriba 'confirmo' explícitamente." >&2
        exit 2
    fi
done

exit 0

#!/usr/bin/env bash
# Dice cuáles de las rutas dadas están protegidas, ANTES de escribir nada.
#
# Existe por el hallazgo I2: /build ejecutaba un plan, escribía el código, y recién
# al llegar a un archivo protegido descubría que no podía tocarlo — dejando la branch
# a medias, con el código escrito y la documentación no. El plan y la lista de
# protegidos nunca se hablaban, así que nada avisaba al aprobarlo.
#
#   bash .workflow/check-plan-paths.sh docs/contracts/api.md backend/app/core/time.py
#   bash .workflow/check-plan-paths.sh < lista-de-rutas.txt
#
# Salida: 0 si todas son escribibles, 1 si alguna está protegida (se listan).
#
# No reimplementa el matcher: le pregunta al propio hook con una entrada sintética,
# para que las dos respuestas no puedan divergir nunca.

set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
HOOK="$ROOT/.claude/hooks/check-protected.sh"

if [ ! -f "$HOOK" ]; then
    echo "⚠️  no encuentro $HOOK — sin hook no hay nada que comprobar." >&2
    exit 0
fi

if [ "$#" -gt 0 ]; then
    RUTAS=("$@")
else
    RUTAS=()
    while IFS= read -r linea; do
        [ -n "$linea" ] && RUTAS+=("$linea")
    done
fi

if [ "${#RUTAS[@]}" -eq 0 ]; then
    echo "uso: bash .workflow/check-plan-paths.sh <ruta>... (o rutas por stdin)" >&2
    exit 2
fi

BLOQUEADAS=0

for ruta in "${RUTAS[@]}"; do
    abs="$ruta"
    [[ "$abs" != /* ]] && abs="$ROOT/$ruta"

    # old_string va con un valor cualquiera: basta para que el hook trate esto como
    # una edición y no como una creación.
    entrada=$(RUTA="$abs" python3 -c '
import json, os
print(json.dumps({"tool_name": "Edit",
                  "tool_input": {"file_path": os.environ["RUTA"], "old_string": "x"}}))')

    salida=$(printf '%s' "$entrada" | CLAUDE_PROJECT_DIR="$ROOT" bash "$HOOK" 2>&1)
    if [ $? -ne 0 ]; then
        BLOQUEADAS=$((BLOQUEADAS + 1))
        echo "🛑 $ruta"
        printf '%s\n' "$salida" | sed 's/^/     /'
    fi
done

echo ""
if [ "$BLOQUEADAS" -gt 0 ]; then
    echo "$BLOQUEADAS de ${#RUTAS[@]} ruta(s) del plan están protegidas."
    echo "Decláralo ANTES de escribir código: el usuario tiene que saber al aprobar el"
    echo "plan qué partes va a tener que aplicar él, no descubrirlo con la branch a medias."
    exit 1
fi

echo "✓ las ${#RUTAS[@]} rutas del plan son escribibles."
exit 0

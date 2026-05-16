#!/usr/bin/env bash
# Al terminar sesión muestra resumen de archivos tocados.
# Usa $CLAUDE_PROJECT_DIR para resolver desde raíz del proyecto.

set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$ROOT" 2>/dev/null || exit 0

if [ -d ".git" ]; then
    CHANGED=$(git status --short 2>/dev/null | head -20)
    if [ -n "$CHANGED" ]; then
        echo ""
        echo "📝 Archivos modificados en esta sesión:"
        echo "$CHANGED"
        echo ""
        echo "👉 Revisa con: git diff"
        echo "👉 Commitea TÚ los cambios. Claude no commitea."
        echo "👉 Recuerda: git add explícito, nunca git add ."
    else
        echo ""
        echo "✅ Working tree limpio al terminar la sesión."
    fi
fi

exit 0

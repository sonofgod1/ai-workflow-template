#!/usr/bin/env bash
# Al terminar la sesión, muestra un resumen de archivos tocados.
# Ayuda a revisar qué cambió antes de commitear.

set -uo pipefail

if [ -d ".git" ]; then
    CHANGED=$(git status --short 2>/dev/null | head -20)
    if [ -n "$CHANGED" ]; then
        echo ""
        echo "📝 Archivos modificados en esta sesión:"
        echo "$CHANGED"
        echo ""
        echo "👉 Revisa con: git diff"
        echo "👉 Commitea TÚ los cambios. Claude no commitea."
    fi
fi

exit 0

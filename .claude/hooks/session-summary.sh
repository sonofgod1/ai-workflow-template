#!/usr/bin/env bash
# Al terminar sesión muestra resumen de archivos tocados y el estado de la
# verificación. Usa $CLAUDE_PROJECT_DIR para resolver desde raíz del proyecto.

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

# ─── Evidencia de verificación ────────────────────────────────────────────────
#
# "Implementación completada" sin haber corrido nada es una promesa, no un
# reporte. Esto compara la marca de tiempo de la última verificación contra el
# archivo modificado más reciente: si el código cambió después, lo verificado
# ya no es lo que hay en disco.

command -v python3 > /dev/null 2>&1 || exit 0

python3 - <<'PYEOF' 2>/dev/null || true
import json, subprocess, sys
from pathlib import Path

def tracked_changes():
    out = subprocess.run(["git", "status", "--porcelain"],
                         capture_output=True, text=True).stdout
    paths = []
    for line in out.splitlines():
        p = line[3:].strip().split(" -> ")[-1].strip('"')
        if not p:
            continue
        # docs, estado del workflow y outputs generados no necesitan verificación
        if p.startswith(("docs/", ".workflow/", "graphify-out/")):
            continue
        if p.endswith(".md"):
            continue
        paths.append(p)
    return paths

changed = [p for p in tracked_changes() if Path(p).is_file()]
if not changed:
    sys.exit(0)

newest = max(Path(p).stat().st_mtime for p in changed)
evidence = Path(".workflow/.last-verify.json")

print()
if not evidence.exists():
    print("⚠️  Hay código modificado y ninguna verificación en esta sesión.")
    print("   No declares el trabajo terminado sin evidencia:")
    print("     bash .workflow/verify.sh")
    sys.exit(0)

data = json.loads(evidence.read_text(encoding="utf-8"))
if evidence.stat().st_mtime < newest:
    print("⚠️  La última verificación es ANTERIOR al código que hay en disco.")
    print(f"   Verificado: {data.get('timestamp', '?')} → resultado '{data.get('resultado', '?')}'")
    print("   Vuelve a correr:  bash .workflow/verify.sh")
    sys.exit(0)

resultado = data.get("resultado", "?")
icono = {"ok": "✅", "parcial": "⚠️ ", "falla": "❌"}.get(resultado, "❔")
print(f"{icono} Última verificación: {resultado} ({data.get('timestamp', '?')})")
if resultado != "ok":
    fallidos = [s["paso"] for s in data.get("pasos", []) if s["estado"] != "pass"]
    if fallidos:
        print("   Pasos sin verde: " + ", ".join(fallidos))
PYEOF

exit 0

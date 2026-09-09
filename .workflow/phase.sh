#!/usr/bin/env bash
# .workflow/phase.sh
# Declara en qué fase del workflow está la sesión.
#
# Las restricciones de fase ("no escribes código", "no tocas código de producción")
# vivían solo en el texto de los comandos, así que nada las hacía cumplir: el
# agente podía escribir código en plena revisión. protected.txt ya demostró que
# una regla sin hook es una sugerencia. Esto es el estado que lee ese hook.
#
# Uso:
#   bash .workflow/phase.sh set review "el flujo de login"
#   bash .workflow/phase.sh show
#   bash .workflow/phase.sh clear

set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$ROOT" || exit 1

STATE=".workflow/.phase.json"

# Política de escritura por fase. La fuente de verdad la lee check-phase.sh.
#   docs  — solo docs/. Fases que analizan y reportan, no modifican.
#   tests — docs/ + archivos de test. /test no toca código de producción.
#   full  — cualquier archivo no protegido.
phase_policy() {
  case "$1" in
    discovery|architect|contracts|feature|plan|review|security|ux|deploy|ship) echo "docs" ;;
    test)                                                                 echo "tests" ;;
    implement|build|change|migrate|git-setup)                             echo "full" ;;
    *)                                                                    echo "" ;;
  esac
}

usage() {
  sed -n '2,15p' "$0"
  echo ""
  echo "Fases válidas: discovery architect contracts feature plan implement build test review security ux deploy change migrate git-setup ship"
}

ACTION="${1:-show}"

case "$ACTION" in
  set)
    PHASE="${2:-}"
    TARGET="${3:-}"
    if [ -z "$PHASE" ]; then echo "❌ Falta la fase." >&2; usage; exit 1; fi

    POLICY=$(phase_policy "$PHASE")
    if [ -z "$POLICY" ]; then
      echo "❌ Fase desconocida: '$PHASE'" >&2
      usage
      exit 1
    fi

    mkdir -p .workflow
    PHASE="$PHASE" TARGET="$TARGET" POLICY="$POLICY" python3 - <<'PYEOF'
import json, os, datetime, pathlib
payload = {
    "fase": os.environ["PHASE"],
    "target": os.environ["TARGET"],
    "politica_escritura": os.environ["POLICY"],
    "iniciada": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
}
pathlib.Path(".workflow/.phase.json").write_text(
    json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PYEOF
    echo "📍 Fase: $PHASE (escritura: $POLICY)${TARGET:+ — target: $TARGET}"
    case "$POLICY" in
      docs)  echo "   Solo se puede escribir bajo docs/. Los intentos de tocar código se bloquean." ;;
      tests) echo "   Solo se pueden escribir tests y docs/. El código de producción se bloquea." ;;
      full)  echo "   Escritura libre (respetando .claude/protected.txt)." ;;
    esac
    ;;

  clear)
    rm -f "$STATE"
    echo "📍 Fase limpiada. Escritura sin restricción de fase."
    ;;

  show)
    if [ ! -f "$STATE" ]; then
      echo "📍 Sin fase declarada."
      exit 0
    fi
    python3 -c "
import json
d = json.load(open('$STATE', encoding='utf-8'))
print(f\"📍 Fase: {d['fase']} (escritura: {d['politica_escritura']}) — desde {d['iniciada']}\")
if d.get('target'):
    print(f\"   Target: {d['target']}\")
"
    ;;

  policy)
    phase_policy "${2:-}"
    ;;

  -h|--help)
    usage
    ;;

  *)
    echo "❌ Acción desconocida: '$ACTION'" >&2
    usage
    exit 1
    ;;
esac

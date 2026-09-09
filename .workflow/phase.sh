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

# La fase es de la sesión, y una sesión trabaja en UN worktree. Resolver la raíz
# como CLAUDE_PROJECT_DIR hacía que dos agentes en dos worktrees del mismo repo
# escribieran el mismo archivo: el segundo pisaba la fase del primero en silencio.
# lib-root.sh usa el worktree actual siempre que sea del mismo repositorio.
LIB="$(dirname "${BASH_SOURCE[0]}")/../.claude/hooks/lib-root.sh"
if [ -f "$LIB" ]; then
  # shellcheck source=/dev/null
  . "$LIB"
  ROOT="$(wf_root)"
else
  ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
fi
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

    # Si ya hay una fase puesta desde OTRO worktree, se avisa: es la señal de que
    # dos sesiones comparten estado, y sin decirlo el segundo agente trabaja creyendo
    # que la fase es suya.
    if [ -f "$STATE" ]; then
      ANTERIOR=$(python3 -c "
import json
try:
    print(json.load(open('$STATE', encoding='utf-8')).get('worktree',''))
except Exception:
    print('')
" 2>/dev/null)
      if [ -n "$ANTERIOR" ] && [ "$ANTERIOR" != "$ROOT" ]; then
        echo "⚠️  La fase activa la puso otra sesión, en otro worktree:"
        echo "     $ANTERIOR"
        echo "   Si eso es un agente trabajando, para y dilo: dos sesiones en el mismo"
        echo "   estado se pisan. Un agente por worktree."
      fi
    fi

    mkdir -p .workflow
    BRANCH="$(git branch --show-current 2>/dev/null || echo '')"
    PHASE="$PHASE" TARGET="$TARGET" POLICY="$POLICY" ROOT="$ROOT" \
      BRANCH="$BRANCH" PPID_="$PPID" python3 - <<'PYEOF'
import json, os, datetime, pathlib
payload = {
    "fase": os.environ["PHASE"],
    "target": os.environ["TARGET"],
    "politica_escritura": os.environ["POLICY"],
    "iniciada": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    # Quién y desde dónde: sin esto, una fase heredada de otra sesión es
    # indistinguible de la propia.
    "worktree": os.environ["ROOT"],
    "branch": os.environ["BRANCH"] or None,
    "pid": int(os.environ["PPID_"]),
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
if d.get('branch'):
    print(f\"   Branch: {d['branch']}\")
wt = d.get('worktree')
if wt and wt != '$ROOT':
    print(f\"   ⚠️  Puesta desde otro worktree: {wt}\")
    print('      Dos sesiones compartiendo estado se pisan. Un agente por worktree.')
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

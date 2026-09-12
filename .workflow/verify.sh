#!/usr/bin/env bash
# .workflow/verify.sh
# Contrato único de verificación del proyecto.
#
# Existe para cerrar un agujero: el agente reportaba "implementación completada"
# con una tabla de pruebas manuales y nada obligaba a que hubiera corrido lint,
# type-check ni tests. El reporte era una promesa. Este script produce evidencia:
# un resumen que se pega en el reporte y un .workflow/.last-verify.json que otros
# hooks pueden leer para saber si lo que hay en el working tree fue verificado.
#
# Uso:
#   bash .workflow/verify.sh              # lint + type-check + tests
#   bash .workflow/verify.sh --quick      # solo lint + type-check (sin tests)
#   bash .workflow/verify.sh --strict     # un paso saltado cuenta como fallo (CI)
#   bash .workflow/verify.sh --reusar     # no repetir si la evidencia ya vale
#
# --reusar existe porque un /ship completo corría la suite tres veces sobre el
# MISMO código: la puerta, --abrir-pr otra vez, y pre-push una tercera (hallazgo
# I4). No relaja nada: solo reusa cuando la evidencia describe exactamente este
# árbol — mismo commit, sin cambios sin commitear, y no fue una corrida --quick.
# Ante cualquier duda corre, nunca da por verificado lo que no lo está.
#
# Configuración opcional: .workflow/verify.conf
#   VERIFY_STEPS=(
#     "lint:npm run lint"
#     "typecheck:npm run typecheck"
#     "test:npm test"
#   )
# Si el archivo define VERIFY_STEPS, se usa tal cual y no hay autodetección.
# El proyecto siempre sabe mejor que la heurística.
#
# Deliberadamente SIN `set -e`: los pasos se acumulan para poder reportar cada
# fallo con su causa, igual que git-hooks/pre-commit.

set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$ROOT" || { echo "❌ No pude entrar a $ROOT" >&2; exit 1; }

QUICK=false
STRICT=false
REUSAR=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --quick)  QUICK=true ;;
    --strict) STRICT=true ;;
    --reusar) REUSAR=true ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "❌ Parámetro desconocido: $1" >&2; exit 1 ;;
  esac
  shift
done

# ─── Reusar la evidencia, si describe exactamente este árbol ──────────────────
#
# Un /ship completo corría la suite tres veces sobre el mismo código (hallazgo I4),
# y una puerta cara se termina rodeando con --no-verify. La decisión de reusar es
# una IGUALDAD, no una heurística: mismo commit, sin cambios sin commitear, y no
# fue una corrida --quick. Si falta cualquiera de las tres, se corre.
#
# Nunca se reescribe .last-verify.json al reusar: mover el timestamp haría pasar
# por nueva una verificación vieja, que es justo lo que el archivo sirve para saber.
if $REUSAR && [ -f ".workflow/.last-verify.json" ] && command -v python3 > /dev/null 2>&1; then
  VEREDICTO=$(HEAD_ACTUAL="$(git rev-parse HEAD 2>/dev/null || echo '')"               SUCIO="$(git status --porcelain 2>/dev/null | head -c1)"               QUIERE_QUICK="$QUICK" python3 - <<'PYEOF'
import json, os, sys

try:
    ev = json.load(open(".workflow/.last-verify.json", encoding="utf-8"))
except Exception:
    print("correr	no pude leer la evidencia anterior")
    sys.exit(0)

head = os.environ.get("HEAD_ACTUAL", "")
sucio = bool(os.environ.get("SUCIO", ""))
quiere_quick = os.environ.get("QUIERE_QUICK") == "true"

if not head:
    print("correr	no estoy en un repositorio git")
elif ev.get("git_head") != head:
    print("correr	la evidencia es de otro commit")
elif sucio or ev.get("working_tree_sucio"):
    print("correr	hay cambios sin commitear")
elif ev.get("resultado") == "falla":
    print("correr	la última verificación falló")
elif ev.get("quick") and not quiere_quick:
    print("correr	la evidencia es de una corrida --quick, sin tests")
else:
    print("reusar	%s	%s" % (ev.get("resultado", ""), ev.get("timestamp", "")))
PYEOF
)
  if [ "${VEREDICTO%%	*}" = "reusar" ]; then
    RESTO="${VEREDICTO#*	}"
    echo "♻️  Verificación reusada — mismo commit ($(git rev-parse --short HEAD)), árbol limpio."
    echo "   Resultado: ${RESTO%%	*}  ·  verificado: ${RESTO#*	}"
    echo "   No se corrió de nuevo porque la evidencia describe exactamente este árbol."
    [ "${RESTO%%	*}" = "parcial" ] && echo "   ⚠️  'parcial' no es verde: hubo pasos que nadie corrió."
    exit 0
  fi
  echo "   (no reuso la evidencia anterior: ${VEREDICTO#*	})"
fi

RESULTS=$(mktemp)
LOGDIR=$(mktemp -d)
trap 'rm -rf "$RESULTS" "$LOGDIR"' EXIT

# ─── Definir los pasos ────────────────────────────────────────────────────────

VERIFY_STEPS=()

if [ -f ".workflow/verify.conf" ]; then
  # shellcheck disable=SC1091
  source .workflow/verify.conf
fi

if [ ${#VERIFY_STEPS[@]} -eq 0 ]; then
  # ── Autodetección. Node y Python pueden coexistir (monorepo fullstack), así
  # que cada stack aporta sus propios pasos en vez de competir por uno solo.

  if [ -f "package.json" ]; then
    if [ -x "node_modules/.bin/biome" ]; then
      VERIFY_STEPS+=("lint-js:node_modules/.bin/biome check .")
    elif [ -x "node_modules/.bin/eslint" ]; then
      VERIFY_STEPS+=("lint-js:node_modules/.bin/eslint . --max-warnings=0")
    else
      VERIFY_STEPS+=("lint-js:")
    fi

    if [ -f "tsconfig.json" ] && [ -x "node_modules/.bin/tsc" ]; then
      VERIFY_STEPS+=("typecheck-js:node_modules/.bin/tsc --noEmit --skipLibCheck")
    else
      VERIFY_STEPS+=("typecheck-js:")
    fi

    if grep -q '"test":' package.json 2>/dev/null; then
      VERIFY_STEPS+=("test-js:npm test")
    else
      VERIFY_STEPS+=("test-js:")
    fi
  fi

  if [ -f "pyproject.toml" ] || [ -f "setup.py" ]; then
    if command -v ruff > /dev/null 2>&1; then
      VERIFY_STEPS+=("lint-py:ruff check .")
    else
      VERIFY_STEPS+=("lint-py:")
    fi

    # mypy solo si el proyecto lo configuró: correrlo sin configuración sobre un
    # repo que nunca lo usó produce cientos de errores irrelevantes.
    if command -v mypy > /dev/null 2>&1 && { grep -q '\[tool\.mypy\]' pyproject.toml 2>/dev/null || [ -f "mypy.ini" ]; }; then
      VERIFY_STEPS+=("typecheck-py:mypy .")
    else
      VERIFY_STEPS+=("typecheck-py:")
    fi

    if command -v pytest > /dev/null 2>&1; then
      VERIFY_STEPS+=("test-py:pytest --tb=short -q")
    else
      VERIFY_STEPS+=("test-py:")
    fi
  fi
fi

if [ ${#VERIFY_STEPS[@]} -eq 0 ]; then
  echo "⚠️  No detecté stack (sin package.json, pyproject.toml ni setup.py)."
  echo "   Define los pasos en .workflow/verify.conf para que este proyecto sea verificable."
  echo "   Sin eso, nadie puede afirmar que un cambio está verificado."
  printf 'sin-stack\tskipped\t0\t0\n' >> "$RESULTS"
fi

# ─── Ejecutar ─────────────────────────────────────────────────────────────────

echo "🔬 Verificación del proyecto — $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

for entry in "${VERIFY_STEPS[@]}"; do
  NAME="${entry%%:*}"
  CMD="${entry#*:}"

  if $QUICK && [[ "$NAME" == test-* || "$NAME" == "test" ]]; then
    echo "⏭️  $NAME — saltado (--quick)"
    printf '%s\tskipped\t0\t0\n' "$NAME" >> "$RESULTS"
    continue
  fi

  if [ -z "$CMD" ]; then
    # Un paso vacío puede venir de dos sitios: la autodetección, que lo deja así
    # cuando falta la herramienta, o verify.conf, donde el proyecto lo declaró
    # vacío a conciencia. Decir "sin herramienta instalada" en el segundo caso es
    # mentir sobre por qué algo quedó sin verificar, que es justo lo que este
    # script existe para no hacer.
    if [ -f ".workflow/verify.conf" ] && grep -q "\"$NAME:\"" ".workflow/verify.conf" 2>/dev/null; then
      # Declarado vacío por el proyecto: es una excepción registrada en un archivo
      # versionado y revisable, igual que las de dependencias o de tests. Cuenta
      # como no verificado, pero no como fallo: --strict solo tumba lo que quedó
      # sin correr por accidente, no lo que se decidió a conciencia.
      echo "⚠️  $NAME — declarado sin comando en verify.conf, saltado"
      printf '%s\tskipped-declarado\t0\t0\n' "$NAME" >> "$RESULTS"
    else
      echo "⚠️  $NAME — sin herramienta instalada, saltado"
      printf '%s\tskipped\t0\t0\n' "$NAME" >> "$RESULTS"
    fi
    continue
  fi

  echo "── $NAME: $CMD"
  START=$(date +%s)
  eval "$CMD" > "$LOGDIR/$NAME.log" 2>&1
  CODE=$?
  DURATION=$(( $(date +%s) - START ))

  # pytest devuelve 5 cuando no recolectó ningún test. Un proyecto que todavía
  # no tiene suite no está fallando: está sin verificar, y eso se reporta como
  # saltado para que no se lea como verde.
  if [[ "$NAME" == test-py* ]] && [ $CODE -eq 5 ]; then
    echo "⚠️  $NAME — pytest no encontró tests, saltado"
    printf '%s\tskipped\t0\t%s\n' "$NAME" "$DURATION" >> "$RESULTS"
    continue
  fi

  if [ $CODE -eq 0 ]; then
    echo "✓ $NAME OK (${DURATION}s)"
    printf '%s\tpass\t0\t%s\n' "$NAME" "$DURATION" >> "$RESULTS"
  else
    echo "❌ $NAME falló (exit $CODE, ${DURATION}s)"
    echo ""
    tail -n 40 "$LOGDIR/$NAME.log" | sed 's/^/   /'
    echo ""
    printf '%s\tfail\t%s\t%s\n' "$NAME" "$CODE" "$DURATION" >> "$RESULTS"
  fi
done

# ─── Resumen y evidencia ──────────────────────────────────────────────────────

# `grep -c` imprime 0 y devuelve 1 cuando no hay coincidencias: un `|| echo 0`
# aquí produciría "0\n0" y rompería la comparación numérica de abajo.
PASS=$(grep -c $'\tpass\t'    "$RESULTS" 2>/dev/null || true)
FAIL=$(grep -c $'\tfail\t'    "$RESULTS" 2>/dev/null || true)
SKIP=$(grep -c $'\tskipped\t'           "$RESULTS" 2>/dev/null || true)
SKIP_DECL=$(grep -c $'\tskipped-declarado\t' "$RESULTS" 2>/dev/null || true)
PASS=${PASS:-0}; FAIL=${FAIL:-0}; SKIP=${SKIP:-0}

if [ "$FAIL" -gt 0 ]; then
  OVERALL="falla"
elif [ "$SKIP" -gt 0 ] || [ "$SKIP_DECL" -gt 0 ]; then
  # Las dos clases de saltado dan 'parcial': en los dos casos hay algo sin
  # verificar, y decir 'ok' sería la mentira que este contrato evita. La
  # diferencia solo la usa --strict.
  OVERALL="parcial"
else
  OVERALL="ok"
fi

RESULTS="$RESULTS" OVERALL="$OVERALL" QUICK="$QUICK" python3 - <<'PYEOF'
import json, os, subprocess, datetime, pathlib

def git(*args):
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True).stdout.strip()
    except Exception:
        return ""

steps = []
with open(os.environ["RESULTS"], encoding="utf-8") as fh:
    for line in fh:
        parts = line.rstrip("\n").split("\t")
        if len(parts) != 4:
            continue
        steps.append({
            "paso": parts[0],
            "estado": parts[1],
            "exit_code": int(parts[2]),
            "duracion_s": int(parts[3]),
        })

payload = {
    "version": 1,
    "timestamp": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    "git_head": git("rev-parse", "HEAD"),
    "git_branch": git("branch", "--show-current"),
    # Si el working tree está sucio, la evidencia describe código sin commitear:
    # quien la lea después necesita saberlo para no atribuirla al commit.
    "working_tree_sucio": bool(git("status", "--porcelain")),
    # Sin esto no se puede distinguir una corrida --quick (que salta los tests y
    # por eso da 'parcial') de un 'parcial' legítimo, y --reusar reusaría una
    # verificación sin tests creyendo que los corrió.
    "quick": os.environ.get("QUICK") == "true",
    "resultado": os.environ["OVERALL"],
    "pasos": steps,
}

out = pathlib.Path(".workflow/.last-verify.json")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PYEOF

echo ""
echo "════════════════════════════════════════════════════"
echo "  Verificación: $OVERALL — $PASS ok, $FAIL fallando, $((SKIP + SKIP_DECL)) saltados"
echo "  Commit: $(git rev-parse --short HEAD 2>/dev/null || echo '?')  Branch: $(git branch --show-current 2>/dev/null || echo '?')"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════════════════"

case "$OVERALL" in
  falla)
    echo ""
    echo "❌ No declares el trabajo terminado. Corrige y vuelve a correr."
    exit 1
    ;;
  parcial)
    echo ""
    echo "⚠️  Hay pasos sin verificar. Esto NO es verde:"
    if [ "$SKIP" -gt 0 ]; then
      echo "   Por falta de herramienta:"
      grep $'\tskipped\t' "$RESULTS" 2>/dev/null | cut -f1 | sed 's/^/     - /'
      echo "   Instálala, o decláralo en .workflow/verify.conf con su razón."
    fi
    if [ "$SKIP_DECL" -gt 0 ]; then
      echo "   Declarados sin comando en verify.conf (excepción registrada):"
      grep $'\tskipped-declarado\t' "$RESULTS" 2>/dev/null | cut -f1 | sed 's/^/     - /'
    fi
    # --strict tumba lo que quedó sin correr por accidente. Lo que el proyecto
    # declaró vacío ya es una decisión escrita y revisable: convertirla en fallo
    # obligaría a borrar el paso, y entonces nadie sabría que falta.
    if $STRICT && [ "$SKIP" -gt 0 ]; then
      exit 1
    fi
    exit 0
    ;;
  *)
    exit 0
    ;;
esac

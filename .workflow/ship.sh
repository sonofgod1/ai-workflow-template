#!/usr/bin/env bash
# .workflow/ship.sh
# La puerta antes del PR: corre localmente todo lo que CI va a exigir, y —si el
# proyecto lo autorizó— pushea la branch y abre el PR con su cuerpo generado.
#
# Existe porque "CI es el aprobador" solo funciona si el PR nace verde. Un PR que
# abre en rojo devuelve el trabajo al humano, que es exactamente lo que este flujo
# intenta dejar de hacer.
#
# El merge NO está aquí, y no es un olvido: decidir que algo entra a develop o a
# main es la decisión que se le devuelve al humano. Lo demás es ejecución.
#
# Uso:
#   bash .workflow/ship.sh                 # solo la puerta
#   bash .workflow/ship.sh --abrir-pr      # + push + gh pr create
#   bash .workflow/ship.sh --base main     # base distinta de develop
#   bash .workflow/ship.sh --cuerpo        # imprime el cuerpo del PR y sale

set -uo pipefail

LIB="$(dirname "${BASH_SOURCE[0]}")/../.claude/hooks/lib-root.sh"
# shellcheck source=/dev/null
[ -f "$LIB" ] && . "$LIB"
if command -v wf_root > /dev/null 2>&1; then
  ROOT="$(wf_root)"
else
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi
cd "$ROOT" || exit 1

# La configuración de entrega puede no estar versionada, y entonces un worktree no
# la tiene: sin este fallback, todo lo que corra dentro de un worktree se comporta
# como si el proyecto no hubiera autorizado nada. Se busca en el worktree y, si no
# está, en el checkout principal.
CONF="$ROOT/.workflow/delivery.conf"
if [ ! -f "$CONF" ] && command -v wf_main_root > /dev/null 2>&1; then
  PRINCIPAL="$(wf_main_root)"
  [ -f "$PRINCIPAL/.workflow/delivery.conf" ] && CONF="$PRINCIPAL/.workflow/delivery.conf"
fi
BASE="develop"
ABRIR="no"
SOLO_CUERPO="no"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --abrir-pr) ABRIR="yes" ;;
    --cuerpo)   SOLO_CUERPO="yes" ;;
    --base)     BASE="${2:-develop}"; shift ;;
    -h|--help)  sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "❌ Parámetro desconocido: $1" >&2; exit 1 ;;
  esac
  shift
done

# ── Configuración de entrega ──────────────────────────────────────────────────
# Sin este archivo, el agente no pushea nada: la regla dura 3 sigue en pie y el
# modo PR es una decisión explícita del proyecto, no un cambio que se hereda.
MODO_ENTREGA="local"
AGENTE_PUEDE_PUSHEAR="no"
BASE_POR_DEFECTO=""
# shellcheck source=/dev/null
[ -f "$CONF" ] && source "$CONF"
[ -n "$BASE_POR_DEFECTO" ] && [ "$BASE" = "develop" ] && BASE="$BASE_POR_DEFECTO"

BRANCH="$(git branch --show-current 2>/dev/null)"

# delivery.conf se versiona a propósito, y eso lo vuelve contenido de branch: entre
# que se crea y que se mergea, el modo de entrega del proyecto depende de dónde
# estés parado. /ship fallaba con "este proyecto no autorizó el modo PR" estando
# autorizado — en otra rama —, y ese mensaje manda a revisar una decisión cuando lo
# que falta es un merge. Se busca en la base SOLO para diagnosticar: la autorización
# vale por el árbol que se entrega, no por lo que diga otra rama.
CONF_EN_BASE=""
CONF_EN_RAMA=""
if [ ! -f "$CONF" ]; then
  for REF in "$BASE" "origin/$BASE" develop origin/develop main origin/main; do
    [ -n "$REF" ] || continue
    if git cat-file -e "$REF:.workflow/delivery.conf" 2>/dev/null; then
      CONF_EN_BASE="$REF"
      break
    fi
  done
  # Si no está en ninguna base, puede estar en una branch sin mergear: es lo que
  # pasa cuando se crea la autorización mientras se trabaja en una feature. El
  # proyecto la decidió, pero todavía no la integró, y eso es un diagnóstico
  # distinto del de "nadie la autorizó nunca".
  if [ -z "$CONF_EN_BASE" ]; then
    CONF_EN_RAMA="$(
      for REF in $(git for-each-ref --format='%(refname:short)' refs/heads refs/remotes 2>/dev/null); do
        git cat-file -e "$REF:.workflow/delivery.conf" 2>/dev/null && echo "$REF"
      done | head -1
    )"
  fi
fi

if [ "$SOLO_CUERPO" = "yes" ]; then
  python3 "$ROOT/.workflow/pr-body.py" --base "$BASE"
  exit $?
fi

echo "🚢 ship: preparando $BRANCH → $BASE"
echo ""

FALLAS=()
SALTADOS=()

paso() {
  local nombre="$1"; shift
  echo "── $nombre"
  if "$@"; then
    echo "   ✓ $nombre"
  else
    local code=$?
    if [ $code -eq 127 ]; then
      echo "   ⚠️  $nombre: sin herramienta, saltado"
      SALTADOS+=("$nombre")
    else
      echo "   ❌ $nombre (exit $code)"
      FALLAS+=("$nombre")
    fi
  fi
  echo ""
}

# ── 1. La branch ──────────────────────────────────────────────────────────────
echo "── branch"
if [ -z "$BRANCH" ]; then
  echo "   ❌ HEAD desacoplado: no hay branch desde la que abrir un PR."
  FALLAS+=("branch")
elif [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ] || [ "$BRANCH" = "$BASE" ]; then
  echo "   ❌ Estás en '$BRANCH'. Un PR sale de una branch de trabajo, no de la base."
  FALLAS+=("branch")
else
  echo "   ✓ branch: $BRANCH"
fi
echo ""

# ── 2. Árbol limpio ───────────────────────────────────────────────────────────
# Un PR se abre de lo commiteado. Si queda algo sin commitear, lo que revise el
# humano y lo que corra CI no es lo que hay en tu disco.
echo "── árbol limpio"
# Se excluyen las dos evidencias que el propio andamiaje escribe al correr: en un
# repo creado desde la plantilla van en .gitignore, pero un repo que la adoptó a
# medias las vería como suciedad y la puerta se volvería imposible de pasar.
SUCIO="$(git status --porcelain | grep -v -e '\.workflow/\.last-verify\.json' -e '\.workflow/\.phase\.json')"
if [ -n "$SUCIO" ]; then
  echo "   ❌ Hay cambios sin commitear:"
  echo "$SUCIO" | sed 's/^/      /'
  FALLAS+=("árbol limpio")
else
  echo "   ✓ nada sin commitear"
fi
echo ""

# ── 3. Commits sobre la base ──────────────────────────────────────────────────
echo "── commits sobre $BASE"
if git rev-parse --verify "$BASE" > /dev/null 2>&1; then
  N=$(git rev-list --count "$BASE..HEAD" 2>/dev/null || echo 0)
  if [ "$N" -eq 0 ]; then
    echo "   ❌ Cero commits sobre $BASE: el PR estaría vacío."
    FALLAS+=("commits")
  else
    echo "   ✓ $N commit(s)"
  fi
else
  echo "   ⚠️  la base '$BASE' no existe localmente, saltado"
  SALTADOS+=("commits")
fi
echo ""

# ── 4. Todo lo que CI exige ───────────────────────────────────────────────────
# La verificación no va con --strict a propósito: --strict convierte "saltado" en
# "fallo" y con eso un proyecto sin verify.conf no podría abrir un PR nunca, que es
# la forma más rápida de que la gente deje de usar la puerta. Se lee el resultado
# real de .last-verify.json y se clasifica: 'parcial' es un aviso, 'falla' es rojo.
echo "── verificación"
# --reusar: la puerta suele correrse dos veces seguidas (una para leer el cuerpo,
# otra con --abrir-pr) sobre el mismo commit. verify.sh solo reusa si la evidencia
# describe exactamente este árbol; si no, corre igual. Ver hallazgo I4.
bash "$ROOT/.workflow/verify.sh" --reusar
VERIFY_CODE=$?
RESULTADO=""
if [ -f "$ROOT/.workflow/.last-verify.json" ] && command -v python3 > /dev/null 2>&1; then
  RESULTADO=$(python3 -c "
import json
try:
    print(json.load(open('$ROOT/.workflow/.last-verify.json', encoding='utf-8')).get('resultado',''))
except Exception:
    print('')
" 2>/dev/null)
fi
if [ $VERIFY_CODE -ne 0 ]; then
  echo "   ❌ verificación"
  FALLAS+=("verificación")
elif [ "$RESULTADO" = "parcial" ]; then
  echo "   ⚠️  verificación: parcial, hay pasos que no corrió nadie"
  SALTADOS+=("verificación (parcial)")
elif [ -z "$RESULTADO" ]; then
  echo "   ⚠️  verificación: no pude leer el resultado, no puedo afirmar que fuera completa"
  SALTADOS+=("verificación (resultado ilegible)")
else
  echo "   ✓ verificación"
fi
echo ""

if [ -f "$ROOT/docs/findings.json" ]; then
  paso "índice de hallazgos" python3 "$ROOT/.workflow/findings.py" validate --exigir-test
  paso "decisiones.md al día" python3 "$ROOT/.workflow/findings.py" decisiones --check
else
  echo "── índice de hallazgos"
  echo "   · sin docs/findings.json todavía"
  echo ""
fi

[ -f "$ROOT/.workflow/check-migrations.py" ] && \
  paso "migraciones" python3 "$ROOT/.workflow/check-migrations.py"

[ -f "$ROOT/.workflow/audit-deps.sh" ] && \
  paso "dependencias" bash "$ROOT/.workflow/audit-deps.sh"

# El propio script sale en verde cuando el proyecto no usa Cursor; la condición de
# aquí solo evita el paso cuando no hay nada que comprobar en absoluto.
[ -f "$ROOT/generate-cursor-rules.sh" ] && [ -d "$ROOT/.claude/commands" ] && \
  paso "reglas de Cursor al día" bash "$ROOT/generate-cursor-rules.sh" --check

if compgen -G "$ROOT/.workflow/tests/test-*.py" > /dev/null; then
  echo "── tests del andamiaje"
  ANDAMIAJE_OK=0
  for t in "$ROOT"/.workflow/tests/test-*.py; do
    if ! python3 "$t" > /dev/null 2>&1; then
      echo "   ❌ $(basename "$t")"
      ANDAMIAJE_OK=1
    fi
  done
  if [ $ANDAMIAJE_OK -eq 0 ]; then
    echo "   ✓ tests del andamiaje"
  else
    FALLAS+=("tests del andamiaje")
  fi
  echo ""
fi

# ── Veredicto ─────────────────────────────────────────────────────────────────
echo "════════════════════════════════════════════════════"
if [ ${#FALLAS[@]} -gt 0 ]; then
  echo "  ship: NO listo — ${#FALLAS[@]} paso(s) en rojo"
  printf '     ✗ %s\n' "${FALLAS[@]}"
  echo "════════════════════════════════════════════════════"
  echo ""
  echo "Corrige esto antes de abrir el PR. Un PR que abre en rojo devuelve el"
  echo "trabajo al humano, que es lo que este flujo existe para evitar."
  exit 1
fi

if [ ${#SALTADOS[@]} -gt 0 ]; then
  echo "  ship: listo CON AVISOS — ${#SALTADOS[@]} paso(s) saltado(s)"
  printf '     ⚠️  %s\n' "${SALTADOS[@]}"
  echo "════════════════════════════════════════════════════"
  echo ""
  echo "Saltado localmente no es verde: CI los corre en un entorno limpio y ahí"
  echo "es donde cuentan. El cuerpo del PR lo dice, para que el revisor lo vea."
else
  echo "  ship: listo — todo en verde"
  echo "════════════════════════════════════════════════════"
fi
echo ""

# ── Abrir el PR ───────────────────────────────────────────────────────────────
if [ "$ABRIR" != "yes" ]; then
  echo "Cuerpo del PR:   bash .workflow/ship.sh --cuerpo"
  echo "Abrirlo:         bash .workflow/ship.sh --abrir-pr"
  exit 0
fi

if [ "$MODO_ENTREGA" != "pr" ] || [ "$AGENTE_PUEDE_PUSHEAR" != "si" ]; then
  if [ -n "$CONF_EN_BASE" ]; then
    echo "❌ Esta branch no tiene .workflow/delivery.conf, pero '$CONF_EN_BASE' sí."
    echo ""
    echo "   El modo PR está autorizado en el proyecto: lo que falta no es una"
    echo "   decisión tuya, es traerla a esta branch."
    echo ""
    echo "     git merge $CONF_EN_BASE"
    echo ""
    echo "   No leo la autorización desde la base a propósito: vale por el árbol que"
    echo "   se entrega, no por lo que diga otra rama. Si esta branch de verdad no"
    echo "   debe entregar en PR, el archivo está bien donde está y los comandos"
    echo "   manuales son:"
    echo "     git push -u origin $BRANCH"
    echo "     bash .workflow/ship.sh --cuerpo > /tmp/pr.md"
    echo "     gh pr create --base $BASE --title \"...\" --body-file /tmp/pr.md"
    exit 1
  fi
  if [ -n "$CONF_EN_RAMA" ]; then
    echo "❌ No hay .workflow/delivery.conf en esta branch ni en $BASE."
    echo ""
    echo "   Sí existe en '$CONF_EN_RAMA', que no está mergeada. O sea: alguien"
    echo "   decidió el modo PR, pero el proyecto todavía no lo integró — la"
    echo "   autorización vive en una rama suelta."
    echo ""
    echo "   delivery.conf es una decisión del proyecto: su sitio es $BASE, no una"
    echo "   feature branch. Mergeá '$CONF_EN_RAMA' y volvé a intentarlo."
    echo ""
    echo "   Mientras tanto, los comandos para hacerlo vos:"
    echo "     git push -u origin $BRANCH"
    echo "     bash .workflow/ship.sh --cuerpo > /tmp/pr.md"
    echo "     gh pr create --base $BASE --title \"...\" --body-file /tmp/pr.md"
    exit 1
  fi
  echo "❌ Este proyecto no autorizó el modo PR."
  echo ""
  echo "   Por defecto rige la regla dura 3: los commits y los pushes son del"
  echo "   humano. El modo PR es una decisión de producto por proyecto, no algo"
  echo "   que se herede de la plantilla — cámbialo a conciencia."
  echo ""
  echo "   Para activarlo, crea $CONF — a mano, tú. Está en .claude/protected.txt"
  echo "   precisamente para que el agente no pueda autorizarse a sí mismo:"
  echo ""
  echo "     MODO_ENTREGA=pr           # el agente entrega en PRs, no en tu terminal"
  echo "     AGENTE_PUEDE_PUSHEAR=si   # pushear la branch de trabajo, nunca la base"
  echo "     BASE_POR_DEFECTO=develop"
  echo ""
  echo "   El merge sigue siendo tuyo en los dos modos."
  echo ""
  echo "   Mientras tanto, los comandos para hacerlo tú:"
  echo "     git push -u origin $BRANCH"
  echo "     bash .workflow/ship.sh --cuerpo > /tmp/pr.md"
  echo "     gh pr create --base $BASE --title \"...\" --body-file /tmp/pr.md"
  exit 1
fi

if ! command -v gh > /dev/null 2>&1; then
  echo "⚠️  gh no está instalado: no puedo abrir el PR."
  echo "   La branch sí se puede pushear:  git push -u origin $BRANCH"
  exit 2
fi

echo "── push de $BRANCH"
git push -u origin "$BRANCH" || { echo "   ❌ el push falló"; exit 1; }

CUERPO="$(mktemp)"
python3 "$ROOT/.workflow/pr-body.py" --base "$BASE" --salida "$CUERPO" > /dev/null
TITULO="$(git log -1 --format=%s)"

echo "── gh pr create"
gh pr create --base "$BASE" --head "$BRANCH" --title "$TITULO" --body-file "$CUERPO"
CODE=$?
rm -f "$CUERPO"

if [ $CODE -eq 0 ]; then
  echo ""
  echo "✅ PR abierto. El merge es tuyo: revisa el diff y espera CI en verde."
fi
exit $CODE

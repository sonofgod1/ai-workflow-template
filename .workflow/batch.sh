#!/usr/bin/env bash
# .workflow/batch.sh
# Ejecuta varios planes aprobados en paralelo, cada uno en su worktree, sin
# supervisión, y deja un PR por plan.
#
# Esto es la pieza que convierte el workflow en una fábrica, y por eso es la más
# peligrosa del repositorio: son agentes escribiendo código y abriendo PRs sin
# nadie mirando. Tres condiciones la hacen defendible, y si falta una no la uses:
#
#   1. Los planes están APROBADOS. batch.sh no planifica ni decide: ejecuta. Si un
#      plan tiene decisiones sin resolver, el agente las va a resolver solo, mal, y
#      en paralelo por triplicado.
#   2. Un worktree por plan. Sin aislamiento, dos agentes se pisan los archivos y
#      el estado de fase. Por eso esto vino DESPUÉS de arreglar la fase por
#      worktree, no antes.
#   3. Branch protection con los checks exigidos. El PR es la entrega, y CI es lo
#      único que lo mira antes que un humano.
#
# LO LANZA EL HUMANO. No es un comando del agente: un agente que puede lanzar
# agentes desatendidos multiplica cualquier error suyo por N.
#
# Uso:
#   bash .workflow/batch.sh docs/plans/2026-09-09-a.md docs/plans/2026-09-09-b.md
#   bash .workflow/batch.sh --dry-run docs/plans/*.md
#   bash .workflow/batch.sh --paralelo 3 --base develop docs/plans/*.md

set -uo pipefail

LIB="$(dirname "${BASH_SOURCE[0]}")/../.claude/hooks/lib-root.sh"
# shellcheck source=/dev/null
[ -f "$LIB" ] && . "$LIB"
ROOT="$(command -v wf_root > /dev/null 2>&1 && wf_root || git rev-parse --show-toplevel)"
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
PARALELO=2
DRY="no"
MODELO=""
TIMEOUT_MIN=30
PLANES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)     BASE="${2:-develop}"; shift ;;
    --paralelo) PARALELO="${2:-2}"; shift ;;
    --modelo)   MODELO="${2:-}"; shift ;;
    --timeout)  TIMEOUT_MIN="${2:-30}"; shift ;;
    --dry-run)  DRY="yes" ;;
    -h|--help)  sed -n '2,30p' "$0"; exit 0 ;;
    -*) echo "❌ Parámetro desconocido: $1" >&2; exit 1 ;;
    *) PLANES+=("$1") ;;
  esac
  shift
done

if [ ${#PLANES[@]} -eq 0 ]; then
  echo "❌ Sin planes. Uso: bash .workflow/batch.sh docs/plans/*.md" >&2
  exit 1
fi

# ── Autorización ──────────────────────────────────────────────────────────────
# Además del modo PR, hace falta un permiso propio: entregar en PRs con un humano
# mirando y dejar correr N agentes solos no son el mismo riesgo, así que no pueden
# compartir el mismo interruptor.
MODO_ENTREGA="local"
AGENTE_PUEDE_PUSHEAR="no"
BATCH_HEADLESS="no"
# shellcheck source=/dev/null
[ -f "$CONF" ] && . "$CONF"

if [ "$DRY" != "yes" ]; then
  if [ "$MODO_ENTREGA" != "pr" ] || [ "$AGENTE_PUEDE_PUSHEAR" != "si" ] || [ "$BATCH_HEADLESS" != "si" ]; then
    echo "❌ El modo desatendido no está autorizado en este proyecto."
    echo ""
    echo "   Necesita las tres, en $CONF (que escribes tú: está en protected.txt):"
    echo ""
    echo "     MODO_ENTREGA=pr"
    echo "     AGENTE_PUEDE_PUSHEAR=si"
    echo "     BATCH_HEADLESS=si       # N agentes trabajando sin nadie mirando"
    echo ""
    echo "   Antes de activarlo, comprueba las tres condiciones de la cabecera de"
    echo "   este script. Y prueba con --dry-run, que no necesita autorización."
    exit 1
  fi
  if ! command -v claude > /dev/null 2>&1; then
    echo "❌ 'claude' no está en el PATH: no hay con qué ejecutar los planes." >&2
    exit 1
  fi
fi

if ! git rev-parse --verify "$BASE" > /dev/null 2>&1; then
  echo "❌ La base '$BASE' no existe en este repositorio." >&2
  exit 1
fi

# Un tope duro: el paralelismo lo limita la revisión humana que viene después, no
# la máquina. Diez PRs simultáneos son diez PRs que nadie revisa.
if [ "$PARALELO" -gt 4 ]; then
  echo "⚠️  --paralelo $PARALELO es mucho: lo limito a 4."
  echo "   El cuello de botella pasa a ser la revisión, y N PRs sin revisar no son"
  echo "   progreso. Sube el tope a conciencia editando este script."
  PARALELO=4
fi

WT_DIR="$ROOT/.worktrees"
LOG_DIR="$ROOT/.workflow/.batch-logs"
mkdir -p "$LOG_DIR"

echo "🏭 batch: ${#PLANES[@]} plan(es), $PARALELO en paralelo, base $BASE"
[ "$DRY" = "yes" ] && echo "   (dry-run: no se crea nada)"
echo ""

slug_de() {
  # docs/plans/2026-09-09-refresh-token.md → refresh-token
  local n; n="$(basename "$1" .md)"
  echo "${n#[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-}"
}

# ── Un plan ───────────────────────────────────────────────────────────────────
ejecutar_plan() {
  local plan="$1" slug wt log branch
  slug="$(slug_de "$plan")"
  wt="$WT_DIR/$slug"
  branch="feature/$slug"
  log="$LOG_DIR/$slug.log"

  {
    echo "=== plan: $plan"
    echo "=== branch: $branch"
    echo "=== worktree: $wt"
    echo ""
  } > "$log"

  if git rev-parse --verify "$branch" > /dev/null 2>&1; then
    echo "   ⏭  $slug: la branch $branch ya existe, lo salto" | tee -a "$log"
    echo "SALTADO" > "$log.estado"
    return 0
  fi

  if ! git worktree add -q -b "$branch" "$wt" "$BASE" >> "$log" 2>&1; then
    echo "   ❌ $slug: no se pudo crear el worktree" | tee -a "$log"
    echo "FALLO-WORKTREE" > "$log.estado"
    return 1
  fi

  local argv=(claude -p "/build $plan" --permission-mode acceptEdits
              --output-format text)
  [ -n "$MODELO" ] && argv+=(--model "$MODELO")

  # El plan se ejecuta DENTRO del worktree: así la fase, los hooks y la
  # verificación son los de este trabajo y no los de la sesión de al lado.
  if ! (cd "$wt" && "${argv[@]}") >> "$log" 2>&1; then
    echo "   ❌ $slug: /build falló (ver $log)" | tee -a "$log"
    echo "FALLO-BUILD" > "$log.estado"
    return 1
  fi

  if ! (cd "$wt" && bash .workflow/ship.sh --abrir-pr --base "$BASE") >> "$log" 2>&1; then
    echo "   ❌ $slug: la puerta o el PR fallaron (ver $log)" | tee -a "$log"
    echo "FALLO-SHIP" > "$log.estado"
    return 1
  fi

  echo "   ✅ $slug: PR abierto" | tee -a "$log"
  echo "OK" > "$log.estado"
  # El worktree se quita solo cuando el trabajo ya está en el remoto. Si algo
  # falló, se queda: borrarlo sería borrar la evidencia de por qué falló.
  (cd "$ROOT" && git worktree remove --force "$wt" >> "$log" 2>&1)
  return 0
}

# ── Dry-run ───────────────────────────────────────────────────────────────────
if [ "$DRY" = "yes" ]; then
  for plan in "${PLANES[@]}"; do
    slug="$(slug_de "$plan")"
    estado="crearía"
    [ ! -f "$plan" ] && estado="❌ NO EXISTE"
    git rev-parse --verify "feature/$slug" > /dev/null 2>&1 && estado="⏭ branch ya existe"
    printf '  %-28s %-22s %s\n' "$slug" "$estado" "$WT_DIR/$slug"
  done
  echo ""
  echo "Nada ejecutado. Quita --dry-run para hacerlo de verdad."
  exit 0
fi

for plan in "${PLANES[@]}"; do
  if [ ! -f "$plan" ]; then
    echo "❌ No existe el plan: $plan" >&2
    exit 1
  fi
done

# ── Ejecución por tandas ──────────────────────────────────────────────────────
# Por tandas y no con un semáforo porque `wait -n` es de bash 4.3 y macOS trae
# 3.2. Una tanda espera a la más lenta, pero funciona en todas partes.
i=0
for plan in "${PLANES[@]}"; do
  ejecutar_plan "$plan" &
  i=$((i + 1))
  if [ $((i % PARALELO)) -eq 0 ]; then
    wait
  fi
done
wait

# ── Resumen ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════"
OK=0; FALLOS=0; SALTADOS=0
for plan in "${PLANES[@]}"; do
  slug="$(slug_de "$plan")"
  estado="$(cat "$LOG_DIR/$slug.log.estado" 2>/dev/null || echo "SIN-ESTADO")"
  case "$estado" in
    OK)       printf '  ✅ %-26s PR abierto\n' "$slug"; OK=$((OK + 1)) ;;
    SALTADO)  printf '  ⏭  %-26s la branch ya existía\n' "$slug"; SALTADOS=$((SALTADOS + 1)) ;;
    *)        printf '  ❌ %-26s %s — log: .workflow/.batch-logs/%s.log\n' "$slug" "$estado" "$slug"
              FALLOS=$((FALLOS + 1)) ;;
  esac
done
echo "  $OK con PR, $FALLOS fallando, $SALTADOS saltados"
echo "════════════════════════════════════════════════════"

if [ $FALLOS -gt 0 ]; then
  echo ""
  echo "Los worktrees de los que fallaron siguen en .worktrees/ a propósito:"
  echo "ahí está el estado en el que quedó cada uno. Cuando termines de mirar:"
  echo "   git worktree remove --force .worktrees/[slug]"
  exit 1
fi

echo ""
echo "Ahora te toca revisar los PRs. Ese es el cuello de botella real, y es el"
echo "que no se automatiza: el merge es tuyo."
exit 0

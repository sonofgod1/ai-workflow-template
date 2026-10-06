#!/usr/bin/env bash
# apply-sdd.sh
# Pasa un proyecto con el workflow viejo al loop spec-driven.
#
# Se ejecuta DESDE el clone de la plantilla (esta, con /spec /check /FORMAT.md),
# apuntando al otro repo. No usa GitHub: copia el árbol local. sync-workflow.sh
# sigue siendo para actualizar *después*, cuando SDD ya esté en main.
#
#   bash apply-sdd.sh /ruta/al/proyecto
#   bash apply-sdd.sh /ruta/al/proyecto --dry-run
#   bash apply-sdd.sh /ruta/al/proyecto --force          # árbol sucio
#   bash apply-sdd.sh /ruta/al/proyecto --skip-branch
#   bash apply-sdd.sh /ruta/al/proyecto --skip-hooks
#   bash apply-sdd.sh /ruta/al/proyecto --claude         # intenta `claude -p` para distill
#
# Hace: overlay de andamiaje + hooks + stub de SPEC.md (norte del CLAUDE viejo).
# No hace: commits ni push. Distill de §I/§V es un agente;
# el script deja el prompt. --claude lo lanza si hay CLI.
#
# Nunca pisa: verify.conf, delivery.conf, CODEOWNERS, .github/workflows,
# settings.local.json, el SPEC.md del *template*, un SPEC.md del proyecto
# que ya tenga §G real, ni CLAUDE.md.pre-sdd si ya existe.
# Branch: solo desde main/master/develop, o reusa chore/sdd-workflow.
# Una feature (p. ej. test/invariantes-spec) para: --skip-branch o checkout
# develop/main primero.

set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DRY_RUN=false
FORCE=false
SKIP_BRANCH=false
SKIP_HOOKS=false
RUN_CLAUDE=false
TARGET=""

usage() {
  sed -n '2,22p' "$0" | sed 's/^# \?//'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage 0 ;;
    --dry-run) DRY_RUN=true ;;
    --force) FORCE=true ;;
    --skip-branch) SKIP_BRANCH=true ;;
    --skip-hooks) SKIP_HOOKS=true ;;
    --claude) RUN_CLAUDE=true ;;
    --) shift; break ;;
    -*) echo "❌ Parámetro desconocido: $1" >&2; usage 1 ;;
    *)
      if [[ -n "$TARGET" ]]; then
        echo "❌ Un solo destino. Sobra: $1" >&2
        exit 1
      fi
      TARGET="$1"
      ;;
  esac
  shift
done

if [[ -z "$TARGET" ]]; then
  echo "❌ Falta la ruta del proyecto." >&2
  usage 1
fi

TARGET="$(cd "$TARGET" && pwd)"

if [[ "$TARGET" == "$SRC" ]]; then
  echo "❌ El destino no puede ser la plantilla misma." >&2
  exit 1
fi

if [[ ! -f "$SRC/.claude/commands/spec.md" || ! -f "$SRC/FORMAT.md" ]]; then
  echo "❌ $SRC no parece la plantilla SDD (falta spec.md o FORMAT.md)." >&2
  exit 1
fi

if [[ ! -d "$TARGET/.git" ]]; then
  echo "❌ $TARGET no es un repo git. No borres el historial: git init solo si es nuevo." >&2
  exit 1
fi

run() {
  if $DRY_RUN; then
    echo "   (dry-run) $*"
    return 0
  fi
  "$@"
}

echo "📦 Fuente:  $SRC"
echo "📂 Destino: $TARGET"
$DRY_RUN && echo "🔍 dry-run — no se escribe"

# ── 0. árbol sucio ──────────────────────────────────────────────────────────
if ! $DRY_RUN; then
  dirty="$(git -C "$TARGET" status --porcelain)"
  if [[ -n "$dirty" ]] && ! $FORCE; then
    echo "❌ El destino tiene cambios sin commitear. Commiteá, stash, o --force." >&2
    echo "$dirty" | sed 's/^/   /'
    exit 1
  fi
fi

# ── 1. branch ───────────────────────────────────────────────────────────────
if ! $SKIP_BRANCH; then
  current="$(git -C "$TARGET" branch --show-current || true)"
  existe=false
  if git -C "$TARGET" show-ref --verify --quiet refs/heads/chore/sdd-workflow; then
    existe=true
  fi

  if [[ "$current" == "chore/sdd-workflow" ]]; then
    echo "🌿 ya en chore/sdd-workflow"
  elif $existe; then
    echo "🌿 chore/sdd-workflow ya existe — checkout (no se crea desde $current)"
    run git -C "$TARGET" checkout chore/sdd-workflow
  elif [[ "$current" == "main" || "$current" == "master" || "$current" == "develop" ]]; then
    echo "🌿 branch chore/sdd-workflow desde $current"
    run git -C "$TARGET" checkout -b chore/sdd-workflow
  else
    echo "❌ Estás en '$current', no en main/develop." >&2
    echo "   apply-sdd no crea chore/sdd-workflow desde una feature." >&2
    echo "   git checkout develop   # o main" >&2
    echo "   # o: git checkout chore/sdd-workflow  (si ya existe)" >&2
    echo "   # o: bash apply-sdd.sh … --skip-branch  (overlay sobre esta branch)" >&2
    exit 1
  fi
fi

# ── 2. backup norte ─────────────────────────────────────────────────────────
OLD_CLAUDE="$TARGET/CLAUDE.md"
BACKUP="$TARGET/.claude/CLAUDE.md.pre-sdd"
if [[ -f "$BACKUP" ]]; then
  echo "💾 CLAUDE.md.pre-sdd ya existe — no se pisa"
elif [[ -f "$OLD_CLAUDE" ]]; then
  echo "💾 backup del CLAUDE.md viejo → .claude/CLAUDE.md.pre-sdd"
  if ! $DRY_RUN; then
    mkdir -p "$TARGET/.claude"
    cp "$OLD_CLAUDE" "$BACKUP"
  fi
fi

# ── 3. overlay ──────────────────────────────────────────────────────────────
echo "📄 overlay de andamiaje (sin verify.conf / delivery.conf / CI / CODEOWNERS)"

rsync_cmd() {
  local from="$1" to="$2"
  shift 2
  if $DRY_RUN; then
    echo "   (dry-run) rsync $* $from -> $to"
    return 0
  fi
  mkdir -p "$(dirname "$to")"
  rsync -a --exclude '.DS_Store' "$@" "$from" "$to"
}

rsync_cmd "$SRC/.claude/commands/" "$TARGET/.claude/commands/" --delete
rsync_cmd "$SRC/.claude/agents/" "$TARGET/.claude/agents/" --delete
rsync_cmd "$SRC/.claude/hooks/" "$TARGET/.claude/hooks/"
run cp "$SRC/.claude/settings.json" "$TARGET/.claude/settings.json"
run cp "$SRC/.claude/protected.txt" "$TARGET/.claude/protected.txt"

rsync_cmd "$SRC/.workflow/" "$TARGET/.workflow/" \
  --exclude verify.conf \
  --exclude delivery.conf \
  --exclude '.last-verify.json' \
  --exclude '.phase.json' \
  --exclude '__pycache__' \
  --exclude '.DS_Store'

rsync_cmd "$SRC/git-hooks/" "$TARGET/git-hooks/"
run cp "$SRC/generate-cursor-rules.sh" "$TARGET/generate-cursor-rules.sh"
run cp "$SRC/sync-workflow.sh" "$TARGET/sync-workflow.sh"
run cp "$SRC/apply-sdd.sh" "$TARGET/apply-sdd.sh"
run cp "$SRC/FORMAT.md" "$TARGET/FORMAT.md"
if ! $DRY_RUN; then
  mkdir -p "$TARGET/docs"
fi
run cp "$SRC/docs/workflow.md" "$TARGET/docs/workflow.md"
run cp "$SRC/CLAUDE.md" "$TARGET/CLAUDE.md"

# ── 4. SPEC stub (norte del CLAUDE viejo; no el SPEC de la plantilla) ───────
if ! $DRY_RUN; then
  python3 - "$TARGET" "$BACKUP" <<'PY'
import re, sys
from pathlib import Path

dest = Path(sys.argv[1])
backup = Path(sys.argv[2]) if len(sys.argv) > 2 else Path()
spec = dest / "SPEC.md"

def norte_de(text: str) -> str:
    m = re.search(
        r"\*\*Este sistema existe para:\*\*\s*(.+?)(?=\n\n|\n\*\*|\n### |\n---)",
        text,
        re.S,
    )
    if not m:
        return ""
    g = re.sub(r"\s+", " ", m.group(1)).strip()
    if not g or "[pendiente" in g:
        return ""
    return g

existente = spec.read_text(encoding="utf-8") if spec.exists() else ""
m_g = re.search(r"^## §G GOAL\s*\n(.+?)(?=\n## |\Z)", existente, re.S | re.M)
if m_g:
    body = m_g.group(1).strip()
    if body and "[pendiente" not in body:
        print("📋 SPEC.md ya tiene §G — no se pisa")
        raise SystemExit(0)

norte = ""
if backup.exists():
    norte = norte_de(backup.read_text(encoding="utf-8"))

modo = "spec"
dc = dest / ".workflow" / "delivery.conf"
if (dest / "docs" / "findings.json").exists() or (
    dc.exists() and "MODO_ENTREGA=pr" in dc.read_text(encoding="utf-8")
):
    modo = "production"

g_block = norte if norte else "[pendiente — /spec distill]"
c_extra = ""
disc = dest / "docs" / "discovery"
if disc.is_dir():
    c_extra = "- Hay discovery en `docs/discovery/`: usalo en distill, no lo ignores.\n"

spec.write_text(
    f"""# SPEC

## §G GOAL
{g_block}

## §M MODE
{modo}

## §C CONSTRAINTS
- [pendiente — /spec distill desde el código]
{c_extra}
## §I INTERFACES
- [pendiente — /spec distill]

## §V INVARIANTS
- [pendiente — /spec distill]

## §T TASKS
id|status|task|cites
T1|.|distill §I §V §C del código y contratos; no reescribir §G si ya está|-

## §B BUGS
id|date|cause|fix
-|-|-|-

## §D DELTA
id|op|target|change|cites
-|-|-|-|-
""",
    encoding="utf-8",
)
print("📋 SPEC.md stub escrito (§G desde el CLAUDE viejo)" if norte else "📋 SPEC.md stub (§G pendiente)")
PY
fi

# ── 5. reglas Cursor (no estorba en Claude-only) ────────────────────────────
if [[ -x "$TARGET/generate-cursor-rules.sh" ]] || [[ -f "$TARGET/generate-cursor-rules.sh" ]]; then
  echo "🖥  generate-cursor-rules.sh --force"
  if ! $DRY_RUN; then
    mkdir -p "$TARGET/.cursor/rules"
    (cd "$TARGET" && bash generate-cursor-rules.sh --force)
  fi
fi

# ── 6. hooks (no es git init) ───────────────────────────────────────────────
if ! $SKIP_HOOKS; then
  echo "🪝 reinstalar hooks en .git/hooks/"
  if ! $DRY_RUN; then
    for h in pre-commit commit-msg pre-push; do
      cp "$TARGET/git-hooks/$h" "$TARGET/.git/hooks/$h"
      chmod +x "$TARGET/.git/hooks/$h"
    done
    git -C "$TARGET" config --local core.hooksPath .git/hooks
  fi
fi

# ── 7. prompt distill ───────────────────────────────────────────────────────
PROMPT_FILE="$TARGET/.claude/sdd-distill-prompt.txt"
PROMPT=$(cat <<'EOF'
/spec distill

§G de SPEC.md ya está (o está en .claude/CLAUDE.md.pre-sdd). No lo reescribas salvo que esté [pendiente].
Llená §I, §V y el resto de §C desde el código, tests y docs/contracts/.
§T = huecos reales (TODO, tests faltantes), no un inventario del pasado.
No copies el SPEC.md de la plantilla. Este producto no es el andamiaje.

Cuando termines, paramos. Certifica bash .workflow/verify.sh.
/check es python3 .workflow/check-spec.py y no lee la app. No es puerta.
EOF
)
if ! $DRY_RUN; then
  printf '%s\n' "$PROMPT" > "$PROMPT_FILE"
fi

echo ""
echo "✅ Overlay listo. No hay commit (eso lo hacés vos)."
echo ""
echo "Siguiente (Claude Code, en $TARGET):"
echo "  1. Abrí este repo. Pegá el contenido de .claude/sdd-distill-prompt.txt"
echo "  2. Revisá SPEC.md §G"
echo "  3. bash .workflow/verify.sh     # eso certifica. /check es el script, no un chat"
echo ""

if $RUN_CLAUDE; then
  if $DRY_RUN; then
    echo "   (dry-run) claude -p <sdd-distill-prompt.txt>"
  elif command -v claude >/dev/null 2>&1; then
    echo "🤖 --claude: lanzando distill (esto escribe SPEC.md; no es /check)"
    (cd "$TARGET" && claude -p "$(cat "$PROMPT_FILE")")
  else
    echo "⚠️  --claude pedido pero no hay CLI \`claude\` en PATH. Usá el prompt a mano."
    exit 1
  fi
fi

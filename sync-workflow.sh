#!/usr/bin/env bash
# sync-workflow.sh
# Sincroniza el workflow desde el repo master usando GitHub Tree API.
# Uso: bash sync-workflow.sh [--dry-run]
#
# Requisitos: curl, git, python3
# El repositorio fuente se define en WORKFLOW_REPO a continuación.

set -e

# ─── Configuración ────────────────────────────────────────────────────────────

WORKFLOW_REPO="sonofgod1/ai-workflow-template"
BRANCH="main"
GITHUB_API="https://api.github.com"
RAW_BASE="https://raw.githubusercontent.com/$WORKFLOW_REPO/$BRANCH"

# Archivos y carpetas a sincronizar
SYNC_PATHS=(
  ".claude/commands"
  ".claude/hooks"
  ".claude/settings.json"
  ".claude/protected.txt"
  "git-hooks"
)

# ─── Flags ────────────────────────────────────────────────────────────────────

DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
  DRY_RUN=true
  echo "🔍 Modo dry-run — no se escribirán archivos"
fi

# ─── Helpers ──────────────────────────────────────────────────────────────────

log()  { echo "  $1"; }
ok()   { echo "  ✓ $1"; }
warn() { echo "  ⚠️  $1"; }
err()  { echo "  ❌ $1"; exit 1; }

# ─── Verificar dependencias ───────────────────────────────────────────────────

command -v curl    > /dev/null 2>&1 || err "curl no está instalado."
command -v git     > /dev/null 2>&1 || err "git no está instalado."
command -v python3 > /dev/null 2>&1 || err "python3 no está instalado."

if ! git rev-parse --git-dir > /dev/null 2>&1; then
  err "No estás dentro de un repositorio Git. Ejecuta este script desde la raíz de tu proyecto."
fi

# ─── Protección de CLAUDE.md ──────────────────────────────────────────────────

if [ -f "CLAUDE.md" ]; then
  echo ""
  echo "📋 CLAUDE.md encontrado en este proyecto."
  echo "   Este archivo contiene el norte del proyecto, stack definido y configuración específica."
  echo "   sync-workflow.sh NUNCA sobreescribe CLAUDE.md."
  echo ""
fi

# ─── Obtener árbol de archivos del repo ───────────────────────────────────────

echo ""
echo "🔄 Conectando con GitHub: $WORKFLOW_REPO@$BRANCH"

API_HEADERS=(-H "Accept: application/vnd.github.v3+json")

if [ -n "$GITHUB_TOKEN" ]; then
  API_HEADERS+=(-H "Authorization: token $GITHUB_TOKEN")
fi

TREE_URL="$GITHUB_API/repos/$WORKFLOW_REPO/git/trees/$BRANCH?recursive=1"
TREE_RESPONSE=$(curl -s "${API_HEADERS[@]}" "$TREE_URL")

# Verificar error de API
if echo "$TREE_RESPONSE" | grep -q '"message"'; then
  API_MESSAGE=$(echo "$TREE_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('message', 'Error desconocido'))
" 2>/dev/null || echo "Error desconocido")
  err "Error de GitHub API: $API_MESSAGE"
fi

# ─── Filtrar archivos relevantes ──────────────────────────────────────────────

SYNC_PATTERN=$(IFS='|'; echo "${SYNC_PATHS[*]}")

ALL_FILES=$(echo "$TREE_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data.get('tree', []):
    if item.get('type') == 'blob':
        print(item['path'])
")

FILES=$(echo "$ALL_FILES" | grep -E "^($SYNC_PATTERN)" || true)
FILES=$(echo "$FILES" | grep -v "^$" || true)

if [ -z "$FILES" ]; then
  warn "No se encontraron archivos para sincronizar. Verifica WORKFLOW_REPO y SYNC_PATHS."
  exit 0
fi

FILE_COUNT=$(echo "$FILES" | wc -l | tr -d ' ')
echo "   $FILE_COUNT archivos encontrados."
echo ""

# ─── Sincronizar archivos ─────────────────────────────────────────────────────

UPDATED=0
SKIPPED=0
ERRORS=0

while IFS= read -r FILE_PATH; do
  [ -z "$FILE_PATH" ] && continue

  LOCAL_PATH="./$FILE_PATH"
  RAW_URL="$RAW_BASE/$FILE_PATH"

  if $DRY_RUN; then
    echo "  [dry-run] $FILE_PATH"
    ((UPDATED++)) || true
    continue
  fi

  # Crear directorio si no existe
  DIR=$(dirname "$LOCAL_PATH")
  mkdir -p "$DIR"

  # Descargar archivo
  HTTP_CODE=$(curl -s -o "$LOCAL_PATH.tmp" -w "%{http_code}" "${API_HEADERS[@]}" "$RAW_URL")

  if [ "$HTTP_CODE" = "200" ]; then
    mv "$LOCAL_PATH.tmp" "$LOCAL_PATH"
    # Marcar ejecutables: hooks de Claude y git-hooks
    if [[ "$FILE_PATH" == *.sh ]] || [[ "$FILE_PATH" == git-hooks/* ]]; then
      chmod +x "$LOCAL_PATH"
    fi
    ok "$FILE_PATH"
    ((UPDATED++)) || true
  else
    rm -f "$LOCAL_PATH.tmp"
    warn "$FILE_PATH — HTTP $HTTP_CODE"
    ((ERRORS++)) || true
  fi

done <<< "$FILES"

# ─── Resumen ──────────────────────────────────────────────────────────────────

echo ""
echo "─────────────────────────────────────────────────────────────"
if $DRY_RUN; then
  echo "📋 Dry-run completado — $UPDATED archivos se actualizarían"
else
  echo "✅ Sync completado"
  echo "   Actualizados: $UPDATED"
  [ $ERRORS -gt 0 ] && echo "   Errores:       $ERRORS"
  echo ""
  echo "   CLAUDE.md: no modificado (preservado)"
  echo ""

  if [ $UPDATED -gt 0 ]; then
    echo "   Nota: si los git-hooks cambiaron, reinstálalos con /git-setup"
    echo ""
    echo "   Commit sugerido:"
    echo "   git add .claude/ git-hooks/"
    echo "   git commit -m \"chore: sync workflow desde $WORKFLOW_REPO\""
  fi
fi
echo "─────────────────────────────────────────────────────────────"
echo ""

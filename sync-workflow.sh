#!/usr/bin/env bash
# sync-workflow.sh
# Sincroniza el workflow desde el repo master usando GitHub Tree API.
# Uso: bash sync-workflow.sh [--dry-run] [--editor claude|cursor|all]
#
# Requisitos: curl, git, (jq o python3)
# El repositorio fuente se define en WORKFLOW_REPO a continuación.

set -e

# ─── Configuración ────────────────────────────────────────────────────────────

WORKFLOW_REPO="sonofgod1/ai-workflow-template"
BRANCH="main"
GITHUB_API="https://api.github.com"
RAW_BASE="https://raw.githubusercontent.com/$WORKFLOW_REPO/$BRANCH"

# ─── Flags y Argumentos ───────────────────────────────────────────────────────

DRY_RUN=false
EDITOR="claude" # default para retrocompatibilidad

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true ;;
        --editor) EDITOR="$2"; shift ;;
        *) echo "Parámetro desconocido: $1"; exit 1 ;;
    esac
    shift
done

if $DRY_RUN; then
  echo "🔍 Modo dry-run — no se escribirán archivos"
fi

# Validar editor
if [[ "$EDITOR" != "claude" && "$EDITOR" != "cursor" && "$EDITOR" != "all" ]]; then
    echo "❌ Editor inválido: $EDITOR. Usa 'claude', 'cursor' o 'all'."
    exit 1
fi

echo "🤖 Editor seleccionado: $EDITOR"

# Archivos y carpetas a sincronizar según el editor
SYNC_PATHS=("git-hooks")

if [[ "$EDITOR" == "claude" || "$EDITOR" == "all" ]]; then
    SYNC_PATHS+=(".claude/commands" ".claude/hooks" ".claude/settings.json" ".claude/protected.txt")
fi

if [[ "$EDITOR" == "cursor" || "$EDITOR" == "all" ]]; then
    SYNC_PATHS+=(".cursor/rules")
fi

# ─── Helpers ──────────────────────────────────────────────────────────────────

log()  { echo "  $1"; }
ok()   { echo "  ✓ $1"; }
warn() { echo "  ⚠️  $1"; }
err()  { echo "  ❌ $1"; exit 1; }

# ─── Verificar dependencias ───────────────────────────────────────────────────

command -v curl > /dev/null 2>&1 || err "curl no está instalado."
command -v git  > /dev/null 2>&1 || err "git no está instalado."

HAS_JQ=false
if command -v jq > /dev/null 2>&1; then
    HAS_JQ=true
elif ! command -v python3 > /dev/null 2>&1; then
    err "Ni 'jq' ni 'python3' están instalados. Se requiere al menos uno para parsear JSON."
fi

if ! git rev-parse --git-dir > /dev/null 2>&1; then
  err "No estás dentro de un repositorio Git. Ejecuta este script desde la raíz de tu proyecto."
fi

# ─── Protección de Reglas Globales ────────────────────────────────────────────

if [ -f "CLAUDE.md" ]; then
  echo ""
  echo "📋 CLAUDE.md encontrado en este proyecto."
  echo "   Este archivo contiene el norte del proyecto. sync-workflow.sh NUNCA lo sobreescribe."
fi

if [ -f ".cursorrules" ]; then
  echo ""
  echo "📋 .cursorrules encontrado en este proyecto."
  echo "   Este archivo contiene reglas generales. sync-workflow.sh NUNCA lo sobreescribe."
fi

# ─── Obtener árbol de archivos del repo ───────────────────────────────────────

echo ""
echo "🔄 Conectando con GitHub: $WORKFLOW_REPO@$BRANCH"

API_HEADERS=(-H "Accept: application/vnd.github.v3+json")

if [ -n "$GITHUB_TOKEN" ]; then
  API_HEADERS+=(-H "Authorization: token $GITHUB_TOKEN")
fi

TREE_URL="$GITHUB_API/repos/$WORKFLOW_REPO/git/trees/$BRANCH?recursive=1"
TREE_RESPONSE=$(curl -s -w "\n%{http_code}" "${API_HEADERS[@]}" "$TREE_URL")

HTTP_CODE=$(echo "$TREE_RESPONSE" | tail -n1)
TREE_BODY=$(echo "$TREE_RESPONSE" | sed '$d')

# Manejo de errores HTTP
if [[ "$HTTP_CODE" != "200" ]]; then
    if [[ "$HTTP_CODE" == "403" ]]; then
        err "Error de GitHub API (HTTP 403): Rate Limit excedido. Configura GITHUB_TOKEN o intenta más tarde."
    else
        err "Error de GitHub API (HTTP $HTTP_CODE): $TREE_BODY"
    fi
fi

# Verificar si hay error en el body (por precaución)
if echo "$TREE_BODY" | grep -q '"message"'; then
    if $HAS_JQ; then
        API_MESSAGE=$(echo "$TREE_BODY" | jq -r '.message // "Error desconocido"')
    else
        API_MESSAGE=$(echo "$TREE_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin).get('message', 'Error desconocido'))" 2>/dev/null || echo "Error desconocido")
    fi
    err "Error de GitHub API: $API_MESSAGE"
fi

# ─── Filtrar archivos relevantes ──────────────────────────────────────────────

SYNC_PATTERN=$(IFS='|'; echo "${SYNC_PATHS[*]}")

if $HAS_JQ; then
    ALL_FILES=$(echo "$TREE_BODY" | jq -r '.tree[] | select(.type=="blob") | .path')
else
    ALL_FILES=$(echo "$TREE_BODY" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for item in data.get('tree', []):
    if item.get('type') == 'blob':
        print(item['path'])
")
fi

FILES=$(echo "$ALL_FILES" | grep -E "^($SYNC_PATTERN)" || true)
FILES=$(echo "$FILES" | grep -v "^$" || true)

if [ -z "$FILES" ]; then
  warn "No se encontraron archivos para sincronizar. Verifica WORKFLOW_REPO y SYNC_PATHS."
  exit 0
fi

FILE_COUNT=$(echo "$FILES" | wc -l | tr -d ' ')
echo "   $FILE_COUNT archivos encontrados para sincronizar."
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
  DL_HTTP_CODE=$(curl -s -o "$LOCAL_PATH.tmp" -w "%{http_code}" "${API_HEADERS[@]}" "$RAW_URL")

  if [ "$DL_HTTP_CODE" = "200" ]; then
    mv "$LOCAL_PATH.tmp" "$LOCAL_PATH"
    # Marcar ejecutables: hooks de Claude y git-hooks
    if [[ "$FILE_PATH" == *.sh ]] || [[ "$FILE_PATH" == git-hooks/* ]]; then
      chmod +x "$LOCAL_PATH"
    fi
    ok "$FILE_PATH"
    ((UPDATED++)) || true
  else
    rm -f "$LOCAL_PATH.tmp"
    warn "$FILE_PATH — HTTP $DL_HTTP_CODE"
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
  
  if [ $UPDATED -gt 0 ]; then
    echo "   Nota: Revisa si hay que instalar hooks con /git-setup"
    echo ""
    echo "   Commit sugerido:"
    echo "   git add ${SYNC_PATHS[*]}"
    echo "   git commit -m \"chore: sync workflow desde $WORKFLOW_REPO\""
  fi
fi
echo "─────────────────────────────────────────────────────────────"
echo ""

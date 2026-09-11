#!/usr/bin/env bash
# sync-workflow.sh
# Sincroniza el workflow desde el repo master usando GitHub Tree API.
# Uso: bash sync-workflow.sh [--dry-run] [--force] [--commit] [--editor claude|cursor|all]
#
# Los archivos que difieren del template y no coinciden con lo que este script
# escribió la última vez (.claude/.workflow-sync) se consideran personalizados y
# NO se pisan. --force los sobreescribe.
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
FORCE=false
COMMIT=false
EDITOR="claude" # default para retrocompatibilidad

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dry-run) DRY_RUN=true ;;
        --force) FORCE=true ;;
        --commit) COMMIT=true ;;
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
# sync-workflow.sh y generate-cursor-rules.sh entran aquí: sin ellos, este
# script nunca podía repartir sus propias mejoras a proyectos ya instalados.
# Las herramientas de .workflow/ se listan una por una a propósito: la carpeta
# también guarda estado del proyecto (.phase.json, .last-verify.json) y su
# configuración de verificación (verify.conf). Sincronizar la carpeta entera
# pisaría los pasos de verificación que cada proyecto definió para sí mismo.
SYNC_PATHS=("git-hooks" ".github" "sync-workflow.sh")
SYNC_PATHS+=(".workflow/verify.sh" ".workflow/phase.sh")
SYNC_PATHS+=(".workflow/write-guard.py" ".workflow/findings.py")
SYNC_PATHS+=(".workflow/audit-deps.sh" ".workflow/check-migrations.py")
SYNC_PATHS+=(".workflow/danger-scan.py" ".workflow/tests")
SYNC_PATHS+=(".workflow/check-tools.sh" ".workflow/check-regression.py")
SYNC_PATHS+=(".workflow/ship.sh" ".workflow/pr-body.py" ".workflow/batch.sh")
SYNC_PATHS+=(".workflow/check-plan-paths.sh")
# delivery.conf NO va aquí: es la autorización de entrega de cada proyecto, y
# repartirla desde el template le concedería a otro repo un permiso que su dueño
# no dio. Es lo contrario de lo que protected.txt protege.

if [[ "$EDITOR" == "claude" || "$EDITOR" == "all" ]]; then
    SYNC_PATHS+=(".claude/commands" ".claude/hooks" ".claude/agents" ".claude/settings.json" ".claude/protected.txt")
    SYNC_PATHS+=("generate-cursor-rules.sh")
fi

if [[ "$EDITOR" == "cursor" || "$EDITOR" == "all" ]]; then
    SYNC_PATHS+=(".cursor/rules")
fi

# ─── Helpers ──────────────────────────────────────────────────────────────────

# Manifiesto de lo que el sync escribió la última vez. Sin él no se puede
# distinguir "el template avanzó" de "el usuario personalizó este archivo":
# los dos casos se ven igual como "difiere del remoto".
MANIFEST=".claude/.workflow-sync"

sha() { shasum -a 256 "$1" 2>/dev/null | cut -d" " -f1; }

manifest_hash() {
  [ -f "$MANIFEST" ] || return 0
  grep -F "  $1" "$MANIFEST" 2>/dev/null | tail -n1 | cut -d" " -f1
}

manifest_record() {
  mkdir -p "$(dirname "$MANIFEST")"
  [ -f "$MANIFEST" ] && grep -vF "  $1" "$MANIFEST" > "$MANIFEST.tmp" 2>/dev/null || : > "$MANIFEST.tmp"
  echo "$2  $1" >> "$MANIFEST.tmp"
  mv "$MANIFEST.tmp" "$MANIFEST"
}

# Archivos que el sync escribió y todavía no están commiteados, vengan de ESTA
# corrida o de una anterior. Es la pregunta correcta para --commit: UPDATED_LIST
# muere con el proceso, y el sync se parte en dos corridas cada vez que el propio
# script cambia (bash no puede sobreescribirse en marcha). La primera corrida es
# justo la que mueve más archivos, y es la que no tiene el flag — hallazgo B2.
#
# El manifest ya guarda el hash de lo que el sync escribió. Si el archivo en disco
# coincide con ese hash, es obra del sync; si lo personalizaste, no coincide y queda
# fuera solo, sin necesidad de listas de exclusión.
obra_del_sync_sin_commitear() {
  [ -f "$MANIFEST" ] || return 0
  while read -r REGISTRADO RUTA; do
    [ -z "$RUTA" ] && continue
    [ -f "$RUTA" ] || continue
    [ "$(sha "$RUTA")" = "$REGISTRADO" ] || continue
    # Sin cambios frente a HEAD (ya commiteado, o idéntico): nada que hacer.
    if git diff --quiet HEAD -- "$RUTA" 2>/dev/null && git ls-files --error-unmatch "$RUTA" > /dev/null 2>&1; then
      continue
    fi
    echo "$RUTA"
  done < "$MANIFEST"
}

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

if [ -f ".cursor/rules/00-gobernanza.mdc" ]; then
  echo ""
  echo "📋 .cursor/rules/00-gobernanza.mdc encontrado en este proyecto."
  echo "   Es el equivalente de CLAUDE.md para Cursor: lleva el norte del proyecto."
  echo "   sync-workflow.sh NUNCA lo sobreescribe."
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

# Archivos que pertenecen al proyecto, no al template: llevan el norte, el stack
# y la configuración específica. Si ya existen localmente no se tocan, igual que
# CLAUDE.md. Si no existen (instalación nueva) sí se traen, con sus [pendiente].
NEVER_OVERWRITE=(".cursor/rules/00-gobernanza.mdc" ".github/CODEOWNERS")

is_never_overwrite() {
  local candidate="$1" entry
  for entry in "${NEVER_OVERWRITE[@]}"; do
    [ "$entry" = "$candidate" ] && return 0
  done
  return 1
}

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
PRESERVED=0
MODIFIED=0
ERRORS=0
MODIFIED_LIST=""
UPDATED_LIST=""
SELF_UPDATE=false

while IFS= read -r FILE_PATH; do
  [ -z "$FILE_PATH" ] && continue

  LOCAL_PATH="./$FILE_PATH"
  RAW_URL="$RAW_BASE/$FILE_PATH"

  # Bash lee el script por trozos mientras lo ejecuta, así que sobrescribirse a
  # sí mismo en marcha puede hacerle ejecutar basura. Se deja al lado.
  if [ "$FILE_PATH" = "sync-workflow.sh" ] && [ -f "$LOCAL_PATH" ]; then
    DL=$(curl -s -o "$LOCAL_PATH.new" -w "%{http_code}" "${API_HEADERS[@]}" "$RAW_URL")
    if [ "$DL" = "200" ] && ! cmp -s "$LOCAL_PATH.new" "$LOCAL_PATH"; then
      chmod +x "$LOCAL_PATH.new"
      SELF_UPDATE=true
      warn "sync-workflow.sh tiene una versión nueva — descargada como sync-workflow.sh.new"
    else
      rm -f "$LOCAL_PATH.new"
    fi
    continue
  fi

  if is_never_overwrite "$FILE_PATH" && [ -f "$LOCAL_PATH" ]; then
    log "↩︎  $FILE_PATH — preservado (configuración de este proyecto)"
    ((PRESERVED++)) || true
    continue
  fi

  # Crear directorio si no existe
  DIR=$(dirname "$LOCAL_PATH")
  mkdir -p "$DIR"

  # Descargar a .tmp y decidir ANTES de pisar nada.
  DL_HTTP_CODE=$(curl -s -o "$LOCAL_PATH.tmp" -w "%{http_code}" "${API_HEADERS[@]}" "$RAW_URL")

  if [ "$DL_HTTP_CODE" = "200" ]; then
    REMOTE_SHA=$(sha "$LOCAL_PATH.tmp")

    if [ -f "$LOCAL_PATH" ]; then
      LOCAL_SHA=$(sha "$LOCAL_PATH")

      if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
        rm -f "$LOCAL_PATH.tmp"
        manifest_record "$FILE_PATH" "$REMOTE_SHA"
        ((SKIPPED++)) || true
        continue
      fi

      # Difiere del remoto. ¿Lo cambió el template, o lo personalizó el usuario?
      # Si coincide con lo que este script escribió la última vez, nadie lo tocó.
      KNOWN_SHA=$(manifest_hash "$FILE_PATH")
      if [ "$LOCAL_SHA" != "$KNOWN_SHA" ] && ! $FORCE; then
        rm -f "$LOCAL_PATH.tmp"
        warn "$FILE_PATH — modificado localmente, NO se pisa"
        MODIFIED_LIST="$MODIFIED_LIST$FILE_PATH"$'\n'
        ((MODIFIED++)) || true
        continue
      fi
    fi

    if $DRY_RUN; then
      rm -f "$LOCAL_PATH.tmp"
      echo "  [dry-run] $FILE_PATH"
      ((UPDATED++)) || true
      continue
    fi

    mv "$LOCAL_PATH.tmp" "$LOCAL_PATH"
    manifest_record "$FILE_PATH" "$REMOTE_SHA"
    # Marcar ejecutables: hooks de Claude y git-hooks
    if [[ "$FILE_PATH" == *.sh ]] || [[ "$FILE_PATH" == git-hooks/* ]]; then
      chmod +x "$LOCAL_PATH"
    fi
    ok "$FILE_PATH"
    UPDATED_LIST="$UPDATED_LIST$FILE_PATH"$'\n'
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
  echo "   Actualizados:  $UPDATED"
  [ $SKIPPED -gt 0 ]   && echo "   Sin cambios:   $SKIPPED"
  [ $PRESERVED -gt 0 ] && echo "   Preservados:   $PRESERVED"
  [ $MODIFIED -gt 0 ]  && echo "   Conservados:   $MODIFIED (modificados localmente)"
  [ $ERRORS -gt 0 ]    && echo "   Errores:       $ERRORS"
  echo ""
  
  if $SELF_UPDATE; then
    echo ""
    echo "   ⚠️  Este script se actualizó a sí mismo. Para aplicarlo:"
    echo ""
    echo "       mv sync-workflow.sh.new sync-workflow.sh"
    echo "       bash sync-workflow.sh --editor $EDITOR"
    echo ""
    echo "   No se reemplaza solo: bash lee el script mientras lo ejecuta."
  fi

  if [ $MODIFIED -gt 0 ]; then
    echo ""
    echo "   ⚠️  Estos archivos cambiaron respecto al template y se conservaron:"
    echo "$MODIFIED_LIST" | sed '/^$/d;s/^/       /'
    echo ""
    echo "   Puede ser una personalización tuya — /architect ajusta los comandos a la"
    echo "   escala del proyecto — o que se instalaron antes de que existiera el"
    echo "   registro de sincronización. Para ver qué te perderías:"
    echo ""
    echo "       git diff <archivo>          # tus cambios frente al último commit"
    echo ""
    echo "   Si quieres la versión del template de todas formas:"
    echo "       bash sync-workflow.sh --force"
  fi

  # La compuerta NO puede ser "¿actualicé algo en esta corrida?". Cuando el propio
  # script se auto-actualiza, el sync se parte en dos: la primera corrida escribe
  # todo y la segunda, la que lleva --commit, no actualiza nada. Con la compuerta
  # vieja el flag no llegaba ni a ejecutarse y el trabajo quedaba huérfano sin un
  # solo aviso — hallazgo B2.
  PENDIENTES=$(obra_del_sync_sin_commitear)
  NUM=$(echo "$PENDIENTES" | sed '/^$/d' | wc -l | tr -d ' ')

  if [ $UPDATED -gt 0 ] || [ "$NUM" -gt 0 ]; then
    [ $UPDATED -gt 0 ] && echo "   Nota: Revisa si hay que instalar hooks con /git-setup"
    echo ""

    # ─── Cierre del sync: commitear lo que el sync escribió ───────────────────
    #
    # Existe por el hallazgo I1. Una branch de sync no nace de un plan, así que
    # ningún comando del workflow es dueño de su commit: /build commitea lo que
    # implementó y /ship exige árbol limpio. El hueco lo terminaba tapando el
    # humano a mano — justo la acción que el modo PR existe para quitar.
    #
    # Lo hace el script, no el agente, y solo si se lo piden con --commit: la
    # autorización la da quien ejecuta, no quien escribe el archivo. Es el mismo
    # razonamiento que deja delivery.conf en manos del humano.
    #
    # Se commitea la lista exacta de archivos escritos, nunca las carpetas de
    # SYNC_PATHS: el árbol puede tener trabajo tuyo en .workflow/ o .github/, y
    # un "git add .workflow/" se lo llevaría puesto sin avisar. Ese era, además,
    # el defecto del comando que este bloque sugería antes.
    CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")

    if $COMMIT; then
      if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
        warn "no commiteo en $CURRENT_BRANCH: esa rama solo recibe merges."
        echo "       git checkout -b chore/sync-workflow && bash sync-workflow.sh --commit"
      else
        # Lo que el sync escribió y sigue sin commitear, de ESTA corrida y de las
        # anteriores. Ver obra_del_sync_sin_commitear() y el hallazgo B2.
        A_COMMITEAR="$PENDIENTES"
        # git add con la lista explícita, un archivo por línea, sin glob.
        echo "$A_COMMITEAR" | sed '/^$/d' | tr '\n' '\0' | xargs -0 git add --
        if git diff --cached --quiet; then
          warn "no hay nada staged: los archivos escritos ya estaban commiteados."
        else
          COMMIT_MSG="chore: sync workflow desde $WORKFLOW_REPO ($NUM archivos)"
          COMMIT_BODY=$(echo "$A_COMMITEAR" | sed '/^$/d;s/^/- /')
          if git commit -q -m "$COMMIT_MSG" -m "$COMMIT_BODY"; then
            ok "commiteado en $CURRENT_BRANCH: $(git rev-parse --short HEAD)"
            echo "       $NUM archivo(s), listados en el cuerpo del commit."
            [ "$NUM" -gt "$UPDATED" ] && echo "       Incluye $((NUM - UPDATED)) de una corrida anterior del sync."
            [ $MODIFIED -gt 0 ] && echo "       Los conservados NO entraron: son tuyos."
          else
            warn "el commit falló — revisa la salida de arriba (¿hook de pre-commit?)."
          fi
        fi
      fi
    else
      echo "   Para cerrar el sync en un commit:"
      echo ""
      echo "       bash sync-workflow.sh --commit"
      echo ""
      echo "   Commitea exactamente estos $NUM archivo(s), no las carpetas enteras:"
      echo "$PENDIENTES" | sed '/^$/d;s/^/       /' | head -12
      [ "$NUM" -gt 12 ] && echo "       … y $((NUM - 12)) más"
    fi
  fi
fi
echo "─────────────────────────────────────────────────────────────"
echo ""

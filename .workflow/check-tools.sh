#!/usr/bin/env bash
# .workflow/check-tools.sh
# Qué herramientas del workflow están disponibles en esta máquina, y qué se pierde
# sin cada una.
#
# Existe porque las barreras se degradan en silencio: sin gitleaks, el hook de
# secretos imprime un aviso y sigue; sin ruff, el lint de Python se salta. El
# proyecto parece configurado y no lo está. Los dos comandos que preparan el
# entorno —/git-setup en un proyecto nuevo, /discovery en uno existente— llaman a
# esto para que la brecha se vea el primer día y no el día del incidente.
#
# Uso:
#   bash .workflow/check-tools.sh            # informa, exit 0 siempre
#   bash .workflow/check-tools.sh --strict   # exit 1 si falta algo crítico

set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$ROOT" || exit 1

STRICT=false
[ "${1:-}" = "--strict" ] && STRICT=true

FALTAN_CRITICAS=0
FALTAN_UTILES=0

# tiene <binario>
tiene() { command -v "$1" > /dev/null 2>&1; }

# reporta <estado> <nombre> <para qué> <cómo instalar>
#   estado: ok | falta-critica | falta-util | n/a
reporta() {
  case "$1" in
    ok)            printf '  ✓ %-14s %s\n' "$2" "$3" ;;
    n/a)           printf '  ·  %-14s %s\n' "$2" "$3" ;;
    falta-critica) printf '  ❌ %-14s %s\n' "$2" "$3"
                   printf '     %s\n' "$4"
                   FALTAN_CRITICAS=$((FALTAN_CRITICAS + 1)) ;;
    falta-util)    printf '  ⚠️  %-14s %s\n' "$2" "$3"
                   printf '     %s\n' "$4"
                   FALTAN_UTILES=$((FALTAN_UTILES + 1)) ;;
  esac
}

echo "🧰 Herramientas del workflow"
echo ""

# ─── Imprescindibles ──────────────────────────────────────────────────────────

echo "Imprescindibles"
tiene git     && reporta ok "git" "control de versiones" \
              || reporta falta-critica "git" "control de versiones" "instálalo desde git-scm.com"
tiene python3 && reporta ok "python3" "hooks de protección, índice de hallazgos, checkers" \
              || reporta falta-critica "python3" "sin él los hooks fallan CERRADO y bloquean toda escritura" \
                 "brew install python3"
echo ""

# ─── Seguridad ────────────────────────────────────────────────────────────────

echo "Seguridad"
if tiene gitleaks; then
  reporta ok "gitleaks" "detecta secretos ANTES de que entren al historial"
elif docker info > /dev/null 2>&1; then
  reporta ok "gitleaks" "vía docker (más lento, pero funciona)"
else
  reporta falta-critica "gitleaks" \
    "sin él, un secreto solo se detecta en CI: ya está en el historial y hay que rotar la credencial" \
    "brew install gitleaks   ·   https://github.com/gitleaks/gitleaks"
fi

if [ -f "package.json" ]; then
  tiene npm && reporta ok "npm audit" "vulnerabilidades en dependencias Node" \
            || reporta falta-critica "npm" "auditoría de dependencias Node" "instala Node.js"
fi

if [ -f "pyproject.toml" ] || [ -f "setup.py" ] || [ -f "requirements.txt" ]; then
  if tiene pip-audit || tiene safety; then
    reporta ok "pip-audit" "vulnerabilidades en dependencias Python"
  else
    reporta falta-critica "pip-audit" "vulnerabilidades en dependencias Python" \
      "pip install pip-audit"
  fi
fi
echo ""

# ─── Calidad, según el stack detectado ───────────────────────────────────────

echo "Calidad del código"
HAY_STACK=false

# `compgen -G "**/*.py"` no es recursivo sin globstar: en un repo con los .py
# en subcarpetas daba "sin stack" y el lint nunca se echaba en falta.
if [ -n "$(find . -name '*.py' -not -path './.git/*' -not -path '*/node_modules/*' -print -quit 2>/dev/null)" ] || [ -f "pyproject.toml" ]; then
  HAY_STACK=true
  tiene ruff && reporta ok "ruff" "lint y formato de Python" \
             || reporta falta-util "ruff" "sin él, el lint de Python se salta y verify.sh sale 'parcial'" \
                "brew install ruff   ·   o: pip install ruff"
fi

if [ -f "package.json" ]; then
  HAY_STACK=true
  if [ -x "node_modules/.bin/biome" ] || [ -x "node_modules/.bin/eslint" ]; then
    reporta ok "biome/eslint" "lint de JS/TS"
  else
    reporta falta-util "biome/eslint" "sin linter, el lint de JS/TS se salta" \
      "npm i -D @biomejs/biome   ·   o eslint"
  fi
  if [ -f "tsconfig.json" ]; then
    [ -x "node_modules/.bin/tsc" ] && reporta ok "tsc" "type-check de TypeScript" \
      || reporta falta-util "tsc" "hay tsconfig.json pero no tsc: el type-check se salta" "npm i -D typescript"
  fi
fi

$HAY_STACK || reporta n/a "—" "sin stack Node ni Python detectado"
echo ""

# ─── Opcionales ───────────────────────────────────────────────────────────────

echo "Opcionales"
tiene graphify && reporta ok "graphify" "grafo del repo: menos búsquedas a ciegas" \
               || reporta n/a "graphify" "sin grafo; útil en repos de más de 20 archivos"
echo ""

# ─── Resumen ──────────────────────────────────────────────────────────────────

echo "════════════════════════════════════════════════════"
if [ $FALTAN_CRITICAS -eq 0 ] && [ $FALTAN_UTILES -eq 0 ]; then
  echo "  ✅ Todas las herramientas disponibles."
else
  echo "  $FALTAN_CRITICAS crítica(s), $FALTAN_UTILES útil(es) sin instalar"
fi
echo "════════════════════════════════════════════════════"

if [ $FALTAN_CRITICAS -gt 0 ]; then
  echo ""
  echo "Las críticas dejan una barrera desactivada en silencio: el proyecto parece"
  echo "configurado y no lo está. Instálalas antes de escribir código de producción,"
  echo "o decide explícitamente que asumes el riesgo y déjalo por escrito."
  $STRICT && exit 1
fi

exit 0

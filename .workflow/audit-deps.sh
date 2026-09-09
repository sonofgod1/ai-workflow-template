#!/usr/bin/env bash
# .workflow/audit-deps.sh
# Auditoría de dependencias — contrato único, igual que verify.sh.
#
# Antes esto era un checklist dentro de /security que alguien tenía que acordarse
# de correr. Una vulnerabilidad conocida en una dependencia directa no es algo que
# se descubra cuando el humano se acuerda: es algo que la barrera detecta sola.
#
# Uso:
#   bash .workflow/audit-deps.sh              # falla con high/critical
#   bash .workflow/audit-deps.sh --strict     # falla también con moderate (CI de main)
#
# Configuración opcional en .workflow/verify.conf:
#   AUDIT_STEPS=(
#     "npm:npm audit --audit-level=high"
#     "python:pip-audit"
#   )

set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$ROOT" || exit 1

STRICT=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --strict) STRICT=true ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "❌ Parámetro desconocido: $1" >&2; exit 1 ;;
  esac
  shift
done

NIVEL_NPM="high"
$STRICT && NIVEL_NPM="moderate"

AUDIT_STEPS=()
if [ -f ".workflow/verify.conf" ]; then
  # shellcheck disable=SC1091
  source .workflow/verify.conf
fi

if [ ${#AUDIT_STEPS[@]} -eq 0 ]; then
  if [ -f "package.json" ]; then
    if command -v npm > /dev/null 2>&1; then
      AUDIT_STEPS+=("npm:npm audit --audit-level=$NIVEL_NPM")
    else
      AUDIT_STEPS+=("npm:")
    fi
  fi

  if [ -f "pyproject.toml" ] || [ -f "setup.py" ] || [ -f "requirements.txt" ]; then
    if command -v pip-audit > /dev/null 2>&1; then
      AUDIT_STEPS+=("python:pip-audit")
    elif command -v safety > /dev/null 2>&1; then
      AUDIT_STEPS+=("python:safety check")
    else
      AUDIT_STEPS+=("python:")
    fi
  fi

  if [ -f "Cargo.toml" ]; then
    command -v cargo-audit > /dev/null 2>&1 \
      && AUDIT_STEPS+=("rust:cargo audit") || AUDIT_STEPS+=("rust:")
  fi

  if [ -f "Gemfile" ]; then
    command -v bundler-audit > /dev/null 2>&1 \
      && AUDIT_STEPS+=("ruby:bundler-audit check --update") || AUDIT_STEPS+=("ruby:")
  fi

  if [ -f "go.mod" ]; then
    command -v govulncheck > /dev/null 2>&1 \
      && AUDIT_STEPS+=("go:govulncheck ./...") || AUDIT_STEPS+=("go:")
  fi
fi

echo "🔐 Auditoría de dependencias — $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

if [ ${#AUDIT_STEPS[@]} -eq 0 ]; then
  echo "⚠️  No detecté gestor de dependencias. Si este proyecto tiene alguno,"
  echo "   declara AUDIT_STEPS en .workflow/verify.conf."
  exit 0
fi

FALLOS=0
SALTADOS=0
SIN_HERRAMIENTA=()

for entry in "${AUDIT_STEPS[@]}"; do
  NAME="${entry%%:*}"
  CMD="${entry#*:}"

  if [ -z "$CMD" ]; then
    echo "⚠️  $NAME — sin herramienta de auditoría instalada, saltado"
    SALTADOS=$((SALTADOS + 1))
    SIN_HERRAMIENTA+=("$NAME")
    continue
  fi

  echo "── $NAME: $CMD"
  OUT=$(eval "$CMD" 2>&1)
  CODE=$?
  if [ $CODE -eq 0 ]; then
    echo "✓ $NAME — sin vulnerabilidades en el nivel exigido"
  else
    echo "❌ $NAME — vulnerabilidades encontradas:"
    printf '%s\n' "$OUT" | tail -n 60 | sed 's/^/   /'
    FALLOS=$((FALLOS + 1))
  fi
  echo ""
done

echo "════════════════════════════════════════════════════"
echo "  Auditoría: $FALLOS con hallazgos, $SALTADOS saltados (nivel: $NIVEL_NPM+)"
echo "════════════════════════════════════════════════════"

if [ ${#SIN_HERRAMIENTA[@]} -gt 0 ]; then
  echo ""
  echo "⚠️  Sin auditar: ${SIN_HERRAMIENTA[*]}"
  echo "   Instala la herramienta que falta:"
  for h in "${SIN_HERRAMIENTA[@]}"; do
    case "$h" in
      python) echo "     pip install pip-audit" ;;
      rust)   echo "     cargo install cargo-audit" ;;
      ruby)   echo "     gem install bundler-audit" ;;
      go)     echo "     go install golang.org/x/vuln/cmd/govulncheck@latest" ;;
      npm)    echo "     npm no está en el PATH" ;;
    esac
  done
  echo "   Un stack sin auditar no es un stack sin vulnerabilidades."
fi

if [ $FALLOS -gt 0 ]; then
  echo ""
  echo "❌ Hay dependencias vulnerables. Antes de desplegar:"
  echo "   1. Actualiza la dependencia si hay parche disponible."
  echo "   2. Si no lo hay, registra el riesgo aceptado como hallazgo:"
  echo "      python3 .workflow/findings.py add --id [ID] --severidad important \\"
  echo "        --titulo \"CVE sin parche en [dep]\" --origen docs/reviews/[archivo].md"
  echo "   3. Nunca lo dejes sin registrar: una excepción no documentada se vuelve permanente."
  exit 1
fi

if $STRICT && [ $SALTADOS -gt 0 ]; then
  exit 1
fi
exit 0

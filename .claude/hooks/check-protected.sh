#!/usr/bin/env bash
# Bloquea modificaciones a archivos listados en .claude/protected.txt
#
# Excepción para CLAUDE.md: el propio workflow tiene que escribirlo
# (/discovery llena "Norte del proyecto" y "Tipo de proyecto", /architect llena
# "Stack del proyecto" y "Comandos del proyecto"). Bloquearlo entero dejaba esas
# dos fases inejecutables. La política por sección está en $POLICY_PY: se protege
# lo que la regla dura 9 protege — el norte ya definido y las reglas duras — y se
# deja escribir el resto.

set -euo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
PROTECTED_FILE="$ROOT/.claude/protected.txt"
[ -f "$PROTECTED_FILE" ] || exit 0

# Sin python3 no podemos leer la entrada, y un hook de protección que no puede
# decidir tiene que fallar cerrado, no dejar pasar la escritura.
if ! command -v python3 > /dev/null 2>&1; then
    echo "🛑 BLOQUEADO: python3 no está disponible y este hook no puede verificar .claude/protected.txt." >&2
    echo "Instala python3 o desactiva el hook en .claude/settings.json de forma consciente." >&2
    exit 2
fi

INPUT=$(cat)

FILE_PATH=$(printf '%s' "$INPUT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    tool_input = data.get('tool_input', {}) or {}
    print(tool_input.get('file_path', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")

[ -z "$FILE_PATH" ] && exit 0

REL_PATH="${FILE_PATH#$ROOT/}"

# ─── Política por sección para CLAUDE.md ──────────────────────────────────────

read -r -d '' POLICY_PY <<'PY' || true
import json, re, sys

# Secciones que la regla dura 9 protege. El norte solo queda abierto mientras
# siga sin definir ([pendiente]), que es el hueco que /discovery viene a llenar.
NORTE = "Norte del proyecto"
REGLAS = "Reglas duras"

def block(reason):
    print("BLOCK\t" + reason)
    raise SystemExit(0)

claude_md = sys.argv[1]

try:
    data = json.load(sys.stdin)
except Exception:
    block("No pude leer la entrada del hook para verificar la sección.")

tool = data.get("tool_name", "")
tool_input = data.get("tool_input", {}) or {}

if tool == "Write":
    block("Write reemplazaría CLAUDE.md completo. Edita la sección concreta con Edit.")

fragments = []
if tool_input.get("old_string") is not None:
    fragments.append(tool_input["old_string"])
for edit in tool_input.get("edits") or []:
    if edit.get("old_string") is not None:
        fragments.append(edit["old_string"])

if not fragments:
    block("No pude determinar qué parte de CLAUDE.md se está editando.")

try:
    with open(claude_md, encoding="utf-8") as handle:
        text = handle.read()
except OSError:
    block("No pude leer CLAUDE.md para verificar qué sección se toca.")

headings = [(m.start(), m.group(1).strip()) for m in re.finditer(r"(?m)^## (.+)$", text)]

def section_range(index):
    start = headings[index][0]
    end = headings[index + 1][0] if index + 1 < len(headings) else len(text)
    return start, end

protected_ranges = []
for index, (_, title) in enumerate(headings):
    start, end = section_range(index)
    if title.startswith(REGLAS):
        protected_ranges.append((start, end, "Reglas duras"))
    elif title.startswith(NORTE) and "[pendiente" not in text[start:end]:
        protected_ranges.append((start, end, "Norte del proyecto (ya definido)"))

for fragment in fragments:
    if not fragment:
        block("Edit con old_string vacío sobre CLAUDE.md.")
    positions = [m.start() for m in re.finditer(re.escape(fragment), text)]
    if not positions:
        block("El fragmento a editar no aparece en CLAUDE.md.")
    for pos in positions:
        span = (pos, pos + len(fragment))
        for start, end, label in protected_ranges:
            if span[0] < end and start < span[1]:
                block("la edición toca la sección '%s'. Regla dura 9: proponlo, no lo apliques." % label)

print("ALLOW")
PY

claude_md_policy() {
    local verdict
    verdict=$(printf '%s' "$INPUT" | python3 -c "$POLICY_PY" "$ROOT/CLAUDE.md" 2>/dev/null || echo "")

    if [ "$verdict" = "ALLOW" ]; then
        return 0
    fi

    local reason="${verdict#BLOCK$'\t'}"
    [ -z "$verdict" ] && reason="la verificación por sección falló."

    echo "🛑 BLOQUEADO: CLAUDE.md — $reason" >&2
    echo "Secciones escribibles: Tipo de proyecto, Stack del proyecto, Comandos del proyecto," >&2
    echo "y Norte del proyecto mientras siga en [pendiente]." >&2
    return 1
}

# ─── Comparar contra los patrones protegidos ──────────────────────────────────

while IFS= read -r pattern; do
    [[ "$pattern" =~ ^#.*$ || -z "$pattern" ]] && continue
    if [[ "$REL_PATH" == $pattern || "$FILE_PATH" == $pattern ]]; then
        if [ "$REL_PATH" = "CLAUDE.md" ]; then
            claude_md_policy && exit 0
            exit 2
        fi
        echo "🛑 BLOQUEADO: '$REL_PATH' está protegido por .claude/protected.txt (patrón: '$pattern')." >&2
        echo "Si necesitas tocar este archivo, pide permiso explícito al usuario." >&2
        exit 2
    fi
done < "$PROTECTED_FILE"

exit 0

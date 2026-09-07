#!/usr/bin/env bash
# Bloquea comandos peligrosos sin confirmación explícita.
# Funciona correctamente desde cualquier subdirectorio del proyecto.

set -euo pipefail

INPUT=$(cat)

COMMAND=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    tool_input = data.get('tool_input', {})
    print(tool_input.get('command', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")

[ -z "$COMMAND" ] && exit 0

DANGEROUS_PATTERNS=(
    'rm[[:space:]]+-rf?[[:space:]]+/'
    'rm[[:space:]]+-rf?[[:space:]]+\*'
    'rm[[:space:]]+-rf?[[:space:]]+~'
    'git[[:space:]]+push.*--force'
    'git[[:space:]]+push.*-f([[:space:]]|$)'
    'git[[:space:]]+reset[[:space:]]+--hard'
    'git[[:space:]]+clean[[:space:]]+-fd'
    'DROP[[:space:]]+TABLE'
    'DROP[[:space:]]+DATABASE'
    'TRUNCATE'
    'mkfs\.'
    'dd[[:space:]]+if=.*of=/dev'
    ':(){.*};:'
    '>/dev/sda'
    'chmod[[:space:]]+-R[[:space:]]+777'
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
    if [[ "$COMMAND" =~ $pattern ]]; then
        echo "🛑 COMANDO PELIGROSO DETECTADO: $COMMAND" >&2
        echo "Patrón: $pattern" >&2
        echo "Si realmente quieres ejecutar esto, pide al usuario que escriba 'confirmo' explícitamente." >&2
        exit 2
    fi
done

# ─── Borrar y mover archivos protegidos ───────────────────────────────────────
#
# check-protected.sh solo ve Write/Edit/MultiEdit. Un `rm` va por Bash, así que
# sin esto la regla dura 2 ("nunca borres archivos sin confirmación explícita")
# no la hacía cumplir nada: `rm -rf docs/contracts/` pasaba sin más.

ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
ROOT=$(cd "$ROOT" 2>/dev/null && pwd -P || echo "$ROOT")
PROTECTED_FILE="$ROOT/.claude/protected.txt"

[ -f "$PROTECTED_FILE" ] || exit 0
command -v python3 > /dev/null 2>&1 || exit 0

read -r -d '' DELETION_PY <<'PYEOF' || true
import fnmatch, os, re, shlex, sys

cmd = os.environ.get("COMMAND", "")

# Los cuerpos de heredoc son datos, no comandos. Sin quitarlos, un script que
# solo MENCIONA "rm docs/adr/x" dentro de un heredoc quedaba bloqueado.
HEREDOC = re.compile(r"""<<-?\s*['"]?([A-Za-z_][A-Za-z0-9_]*)['"]?\s*$""")

def strip_heredocs(text):
    lines = text.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        found = HEREDOC.search(line)
        i += 1
        if found:
            delim = found.group(1)
            while i < len(lines) and lines[i].strip() != delim:
                i += 1
            if i < len(lines):
                out.append(lines[i])
                i += 1
    return "\n".join(out)

cmd = strip_heredocs(cmd)

protected = []
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#"):
                protected.append(line.lstrip("+"))
except OSError:
    raise SystemExit(0)

VERBS = ("rm", "shred", "truncate", "mv")

for piece in re.split(r"[;&|]+|\n", cmd):
    try:
        parts = shlex.split(piece)
    except ValueError:
        continue
    if not parts:
        continue

    verb = parts[0]
    args = parts[1:]
    if verb == "git" and args and args[0] == "rm":
        args = args[1:]
    elif verb not in VERBS:
        continue

    for arg in args:
        if arg.startswith("-"):
            continue
        # lstrip("./") quitaría el punto de ".env" y de ".claude/": hay que
        # recortar solo el prefijo "./" literal.
        rel = re.sub(r"^(\./)+", "", arg).rstrip("/")
        if not rel:
            continue
        for pattern in protected:
            base = pattern.rstrip("/*")
            # el argumento ES una ruta protegida, o un directorio que la contiene
            if fnmatch.fnmatch(rel, pattern) or rel == base or base.startswith(rel + "/"):
                print(arg + "\t" + pattern)
                raise SystemExit(0)
PYEOF

TARGET=$(COMMAND="$COMMAND" python3 -c "$DELETION_PY" "$PROTECTED_FILE" 2>/dev/null || echo "")

if [ -n "$TARGET" ]; then
    RUTA="${TARGET%%$'\t'*}"
    PATRON="${TARGET##*$'\t'}"
    echo "🛑 BLOQUEADO: '$RUTA' está protegido por .claude/protected.txt (patrón: '$PATRON')." >&2
    echo "Regla dura 2: nunca borres ni muevas archivos protegidos sin confirmación explícita." >&2
    echo "Comando: $COMMAND" >&2
    exit 2
fi

exit 0

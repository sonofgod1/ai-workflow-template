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

# ─── Comandos destructivos ────────────────────────────────────────────────────
#
# Antes esto era un bucle de regex sobre el texto crudo del comando: cualquier
# comando que solo MENCIONARA un patrón dentro de una cadena o un heredoc quedaba
# bloqueado. Documentar esta misma capa de seguridad era imposible desde el agente,
# y el camino de escape natural era que el usuario escribiera "confirmo" por
# costumbre — que es como una barrera deja de valer algo (hallazgo I3).
#
# danger-scan.py distingue invocación de mención mirando la posición de comando:
# un borrado recursivo en posición de comando bloquea; el mismo texto dentro de un
# `echo` pasa, con aviso.

# lib-root.sh resuelve el worktree actual cuando es del mismo repositorio que
# CLAUDE_PROJECT_DIR, y CLAUDE_PROJECT_DIR en cualquier otro caso. Sin eso, dos
# agentes en dos worktrees leen y escriben el estado del checkout principal.
LIB="$(dirname "${BASH_SOURCE[0]}")/lib-root.sh"
if [ -f "$LIB" ]; then
  # shellcheck source=/dev/null
  . "$LIB"
  ROOT="$(wf_root)"
else
  ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
fi
ROOT=$(cd "$ROOT" 2>/dev/null && pwd -P || echo "$ROOT")
SCAN="$ROOT/.workflow/danger-scan.py"

USAR_RESPALDO=yes
if [ -f "$SCAN" ] && command -v python3 > /dev/null 2>&1; then
    USAR_RESPALDO=no
    SCAN_CODE=0
    printf '%s' "$INPUT" | python3 "$SCAN" || SCAN_CODE=$?
    if [ "$SCAN_CODE" -eq 2 ]; then
        exit 2
    fi
fi

if [ "$USAR_RESPALDO" = "yes" ]; then
    # Sin python3 no se puede hacer el análisis fino. Se vuelve al bucle original:
    # falsos positivos, pero ningún falso negativo. De los dos fallos posibles en un
    # control de seguridad, este es el aceptable.
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
            echo "Patrón: $pattern (análisis de respaldo: python3 no disponible)" >&2
            echo "Si realmente quieres ejecutar esto, pide al usuario que escriba 'confirmo'." >&2
            exit 2
        fi
    done
fi

# ─── Borrar y mover archivos protegidos ───────────────────────────────────────
#
# check-protected.sh solo ve Write/Edit/MultiEdit. Un `rm` va por Bash, así que
# sin esto la regla dura 2 ("nunca borres archivos sin confirmación explícita")
# no la hacía cumplir nada: `rm -rf docs/contracts/` pasaba sin más.

PROTECTED_FILE="$ROOT/.claude/protected.txt"
[ -f "$ROOT/.claude/protected.local.txt" ] && PROTECTED_FILE="$ROOT/.claude/protected.local.txt"

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
excepciones = []
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # '!' = excepción: anula la protección de un patrón más amplio.
            if line.startswith("!"):
                excepciones.append(line[1:])
            else:
                protected.append(line.lstrip("+"))
except OSError:
    raise SystemExit(0)

def exento(rel):
    for pattern in excepciones:
        base = pattern.rstrip("/*")
        if fnmatch.fnmatch(rel, pattern) or rel == base or rel.startswith(base + "/"):
            return True
    return False

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
        if not rel or exento(rel):
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

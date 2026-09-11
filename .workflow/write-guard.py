#!/usr/bin/env python3
"""Guardia de escrituras para los hooks de Claude Code.

Cubre dos agujeros del enforcement anterior:

1. `.claude/hooks/check-protected.sh` solo ve Write/Edit/MultiEdit, y
   `check-bash.sh` solo mira verbos de borrado (rm, mv, truncate). Una
   redirección bastaba para saltarse toda la capa de protección:
   `cat > CLAUDE.md <<EOF` pasaba sin bloqueo.

2. Las restricciones de fase ("no escribes código") vivían solo en el texto de
   los comandos. Nada las hacía cumplir.

Modos:
    write-guard.py targets      # stdin: JSON del hook → stdout: rutas escritas
    write-guard.py check        # stdin: JSON del hook → bloquea (exit 2) o pasa

Limitación honesta: esto es una barandilla, no un sandbox. De un intérprete se
cubren las formas literales de escritura — la ruta en la propia llamada, o en un
Path()/open() que luego se escribe por su variable. Una ruta calculada en tiempo
de ejecución sigue escapando. Cubre lo que un agente hace por accidente o por
atajo, que es el 99% del riesgo real.
"""

import fnmatch
import json
import os
import re
import shlex
import sys
from pathlib import Path

# ── Extracción de rutas escritas ─────────────────────────────────────────────

HEREDOC = re.compile(r"""<<-?\s*['"]?([A-Za-z_][A-Za-z0-9_]*)['"]?\s*$""")

# Redirecciones que no tocan el filesystem del proyecto.
NULL_TARGETS = {"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty"}

REDIRECT = re.compile(r"^(?:[0-9]*|&)?>>?$")
REDIRECT_GLUED = re.compile(r"^(?:[0-9]*|&)?>>?(?=\S)")

# Un script de sed no es un archivo: `sed -i "" 's/a/b/' f.py` no escribe en "s/a/b/".
SED_EXPR = re.compile(r"^[sy]([/|,#:@]).*\1")


def strip_heredocs(text):
    """El cuerpo de un heredoc es dato, no comando: sin quitarlo, un script que
    solo menciona una ruta protegida dentro del texto quedaba bloqueado."""
    lines = text.split("\n")
    out, i = [], 0
    while i < len(lines):
        out.append(lines[i])
        found = HEREDOC.search(lines[i])
        i += 1
        if found:
            delim = found.group(1)
            while i < len(lines) and lines[i].strip() != delim:
                i += 1
            if i < len(lines):
                out.append(lines[i])
                i += 1
    return "\n".join(out)


def _plain_args(tokens):
    return [t for t in tokens if not t.startswith("-")]


def _segment_targets(tokens):
    """Rutas que este segmento de comando escribiría."""
    targets = []

    # 1. Redirecciones: `> f`, `>>f`, `2> f`, `&> f`
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if REDIRECT.match(tok):
            if i + 1 < len(tokens):
                targets.append(tokens[i + 1])
            i += 2
            continue
        glued = REDIRECT_GLUED.match(tok)
        if glued:
            targets.append(tok[glued.end():])
        i += 1

    words = [t for t in tokens if not REDIRECT.match(t) and not REDIRECT_GLUED.match(t)]
    if not words:
        return targets

    verb = os.path.basename(words[0])
    args = words[1:]

    if verb == "git":
        # `git checkout -- ruta` y `git restore ruta` sobreescriben el archivo
        # con la versión del índice: es una escritura destructiva.
        if args and args[0] in ("checkout", "restore"):
            rest = args[1:]
            if "--" in rest:
                rest = rest[rest.index("--") + 1:]
            targets += _plain_args(rest)
        return targets

    if verb in ("tee",):
        targets += _plain_args(args)

    elif verb in ("cp", "install", "rsync"):
        plain = _plain_args(args)
        if len(plain) >= 2:
            targets.append(plain[-1])

    elif verb == "ln":
        plain = _plain_args(args)
        if plain:
            targets.append(plain[-1])

    elif verb in ("touch",):
        targets += _plain_args(args)

    elif verb in ("sed", "perl", "ruby"):
        # Solo en modo in-place. Para sed, el primer argumento suelto es el
        # script, no un archivo.
        if any(a == "-i" or a.startswith("-i") for a in args):
            plain = [a for a in _plain_args(args) if a]
            exprs = [a for a in plain if SED_EXPR.match(a)]
            files = [a for a in plain if not SED_EXPR.match(a)]
            # El script va como -e/-f, o se reconoció por su forma, o es el
            # primer argumento suelto. Solo en el último caso hay que descartarlo.
            if any(a in ("-e", "-f") for a in args) or exprs:
                targets += files
            else:
                targets += files[1:]

    elif verb == "dd":
        for a in args:
            if a.startswith("of="):
                targets.append(a[3:])

    return targets


# ── Escrituras desde el cuerpo de un intérprete ───────────────────────────────
#
# La limitación que este módulo declaraba abajo era real y se cobró su caso: un
# `python3 - <<EOF` que abre el archivo desde dentro no tiene redirección que ver,
# así que pasaba entero. Es el camino más natural para editar un archivo desde
# Bash, no un rebuscamiento.
#
# No se puede analizar Python arbitrario. Sí se pueden cubrir las formas literales,
# que es lo que se escribe por atajo: la ruta en la propia llamada de escritura, o
# la ruta en un Path()/open() que luego se escribe por su variable.

INTERPRETE = re.compile(r"(?:^|[;&|]|\$\(|\s)(?:sudo\s+)?(?:python3?|node|ruby|perl|php)\b")

_R = r"""['"]([^'"\n]{1,300})['"]"""

# La ruta va pegada a la escritura: no hace falta seguir ninguna variable.
ESCRITURA_DIRECTA = [
    re.compile(r"\bopen\s*\(\s*" + _R + r"\s*,\s*['\"][rbt+]*[wax]"),
    re.compile(r"\bPath\s*\(\s*" + _R + r"\s*\)\s*\.\s*"
               r"(?:write_text|write_bytes|unlink|touch|mkdir|rename|replace)"),
    re.compile(r"\bos\.(?:remove|unlink|rename|replace|truncate)\s*\(\s*" + _R),
    re.compile(r"\bshutil\.rmtree\s*\(\s*" + _R),
    re.compile(r"\bshutil\.(?:copy2?|copyfile|move)\s*\([^,)]+,\s*" + _R),
    re.compile(r"\b(?:write|append|truncate)File(?:Sync)?\s*\(\s*" + _R),
    re.compile(r"\bFile\.(?:write|delete)\s*\(\s*" + _R),
]

# La ruta entra en una variable y se escribe por ella. Dos pasos, sin dataflow de
# verdad: el nombre tiene que ser el mismo literal en los dos sitios.
ASIGNA_RUTA = re.compile(r"\b([A-Za-z_]\w*)\s*=\s*(?:Path|open)\s*\(\s*" + _R)
ESCRIBE_VAR = r"\b{}\s*\.\s*(?:write_text|write_bytes|write|writelines|unlink|touch)\b"


def rutas_escritas_en_codigo(codigo):
    """Rutas que este código fuente escribe, por las formas literales conocidas."""
    encontradas = []
    for rx in ESCRITURA_DIRECTA:
        for m in rx.finditer(codigo):
            encontradas.append(m.group(1))
    for m in ASIGNA_RUTA.finditer(codigo):
        var, ruta = m.group(1), m.group(2)
        if re.search(ESCRIBE_VAR.format(re.escape(var)), codigo):
            encontradas.append(ruta)
    return encontradas


def cuerpos_de_codigo(text):
    """Trozos de este comando que un intérprete va a ejecutar como código fuente:
    cuerpos de heredoc y argumentos de -c / -e."""
    cuerpos = []

    lineas = text.split("\n")
    i = 0
    while i < len(lineas):
        apertura = lineas[i]
        found = HEREDOC.search(apertura)
        i += 1
        if not found:
            continue
        delim = found.group(1)
        cuerpo = []
        while i < len(lineas) and lineas[i].strip() != delim:
            cuerpo.append(lineas[i])
            i += 1
        i += 1
        if INTERPRETE.search(apertura):
            cuerpos.append("\n".join(cuerpo))

    for pieza in re.split(r"(?:\|\||&&|[;&|\n])+", text):
        if not INTERPRETE.search(pieza):
            continue
        try:
            tokens = shlex.split(pieza, posix=True)
        except ValueError:
            continue
        for j, tok in enumerate(tokens):
            if tok in ("-c", "-e") and j + 1 < len(tokens):
                cuerpos.append(tokens[j + 1])
    return cuerpos


def command_targets(cmd):
    cmd_original = cmd
    cmd = strip_heredocs(cmd)
    found = []
    for piece in re.split(r"(?:\|\||&&|[;&|\n])+", cmd):
        piece = piece.strip()
        if not piece:
            continue
        try:
            tokens = shlex.split(piece, posix=True)
        except ValueError:
            continue
        if tokens:
            found += _segment_targets(tokens)

    for codigo in cuerpos_de_codigo(cmd_original):
        found += rutas_escritas_en_codigo(codigo)

    out = []
    for raw in found:
        if not raw or raw in NULL_TARGETS or raw.startswith("&"):
            continue
        # lstrip("./") le quitaría el punto a ".env": hay que recortar solo el
        # prefijo "./" literal.
        rel = re.sub(r"^(\./)+", "", raw).rstrip("/")
        if rel and rel not in out:
            out.append(rel)
    return out


# ── Políticas ────────────────────────────────────────────────────────────────

TEST_PATTERNS = [
    "tests/**", "test/**", "spec/**", "**/__tests__/**", "**/tests/**", "**/test/**",
    "**/test_*.py", "**/*_test.py", "**/*_test.go", "**/*.test.*", "**/*.spec.*",
    "conftest.py", "**/conftest.py",
]

DOCS_PATTERNS = ["docs/**"]

# Una fase de escritura limitada tiene que poder dejar su reporte y su rastro.
ALWAYS_ALLOWED = [".workflow/**", "graphify-out/**"]

STALE_HOURS = 12


def matches_any(path, patterns):
    for pat in patterns:
        if fnmatch.fnmatch(path, pat):
            return True
        # fnmatch no trata "**" como multi-nivel: docs/a/b.md no casa con docs/**
        base = pat.rstrip("/*")
        if base and (path == base or path.startswith(base + "/")):
            return True
    return False


def load_protected(root):
    """Devuelve (patrones, excepciones).

    Una excepción ('!ruta') anula la protección aunque un patrón más amplio la
    cubra: '.git/**' protege el repositorio, pero /git-setup tiene que poder
    instalar los hooks en .git/hooks/.
    """
    excepciones = []
    entries = []
    # La lista local, si existe, reemplaza a la sincronizada. Ver el comentario
    # en check-protected.sh: sirve para repositorios donde los archivos que
    # protected.txt protege son el código fuente.
    path = root / ".claude" / "protected.local.txt"
    if not path.exists():
        path = root / ".claude" / "protected.txt"
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("!"):
                excepciones.append(line[1:])
                continue
            entries.append((line.lstrip("+"), line.startswith("+")))
    except OSError:
        pass
    return entries, excepciones


def load_phase(root):
    path = root / ".workflow" / ".phase.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    # Una fase olvidada no debe bloquear el repo para siempre.
    import datetime
    try:
        started = datetime.datetime.fromisoformat(data["iniciada"])
        age = (datetime.datetime.now(started.tzinfo) - started).total_seconds() / 3600
        if age > STALE_HOURS:
            return None
    except (KeyError, ValueError):
        return None
    return data


def relativize(root, target):
    p = Path(target)
    if p.is_absolute():
        try:
            return str(p.resolve().relative_to(root.resolve()))
        except ValueError:
            return None  # fuera del proyecto: no es asunto de estas políticas
    return str(p)


# ── Modos ────────────────────────────────────────────────────────────────────

def read_hook_input():
    try:
        return json.load(sys.stdin)
    except (ValueError, OSError):
        return {}


def extract_targets(data):
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}
    if "command" in tool_input:
        return command_targets(tool_input.get("command", "")), tool or "Bash"
    single = tool_input.get("file_path") or tool_input.get("notebook_path")
    if single:
        return [single], tool or "Write"
    return [], tool


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())

    data = read_hook_input()
    targets, tool = extract_targets(data)

    if mode == "targets":
        for t in targets:
            print(t)
        return 0

    if not targets:
        return 0

    protected, excepciones = load_protected(root)
    phase = load_phase(root)

    for target in targets:
        rel = relativize(root, target)
        if rel is None or not rel:
            continue

        # Una excepción explícita gana sobre cualquier patrón.
        if matches_any(rel, excepciones):
            continue

        # 1. Archivos protegidos — solo para Bash: Write/Edit ya los cubre
        #    check-protected.sh, que además entiende el prefijo '+'.
        if tool == "Bash":
            for pattern, create_only in protected:
                if not matches_any(rel, [pattern]):
                    continue
                if create_only and not (root / rel).exists():
                    continue  # '+' = se puede crear, no modificar
                sys.stderr.write(
                    f"🛑 BLOQUEADO: el comando escribiría en '{rel}', protegido por "
                    f".claude/protected.txt (patrón: '{pattern}').\n"
                    "Regla dura 1: no modifiques archivos protegidos sin confirmación explícita.\n"
                )
                return 2

        # 2. Política de fase
        if phase:
            policy = phase.get("politica_escritura", "full")
            if policy == "full":
                continue
            if matches_any(rel, ALWAYS_ALLOWED) or matches_any(rel, DOCS_PATTERNS):
                continue
            if policy == "tests" and matches_any(rel, TEST_PATTERNS):
                continue

            fase = phase.get("fase", "?")
            que = ("solo puede escribir bajo docs/" if policy == "docs"
                   else "solo puede escribir tests y docs/")
            sys.stderr.write(
                f"🛑 BLOQUEADO por la fase activa: /{fase} {que}.\n"
                f"Intento de escritura en: {rel}\n\n"
                f"La fase /{fase} analiza y reporta; no modifica código. Si de verdad "
                "hay que escribir aquí, termina la fase primero:\n"
                "  bash .workflow/phase.sh clear\n"
                "y dile al usuario por qué la fase se quedó corta.\n"
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())

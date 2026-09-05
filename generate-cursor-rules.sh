#!/usr/bin/env bash
# generate-cursor-rules.sh
# Genera .cursor/rules/*.mdc desde .claude/commands/*.md y CLAUDE.md.
#
# Los archivos de Claude Code son la ÚNICA fuente de verdad. Las reglas de
# Cursor son un derivado: no se editan a mano, se regeneran. Editarlas
# directamente es cómo implement.mdc terminó con el 13% de su contenido.
#
# Uso:
#   bash generate-cursor-rules.sh            # regenera .cursor/rules/
#   bash generate-cursor-rules.sh --check    # falla si están desactualizadas (CI)
#   bash generate-cursor-rules.sh --force    # regenera también 00-gobernanza.mdc
#
# Requisitos: python3

set -euo pipefail

MODE="write"
FORCE="no"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) MODE="check" ;;
    --force) FORCE="yes" ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "❌ Parámetro desconocido: $1" >&2; exit 1 ;;
  esac
  shift
done

command -v python3 > /dev/null 2>&1 || { echo "❌ python3 no está instalado." >&2; exit 1; }

[ -d ".claude/commands" ] || { echo "❌ No encuentro .claude/commands/. Ejecuta desde la raíz del template." >&2; exit 1; }
[ -f "CLAUDE.md" ]        || { echo "❌ No encuentro CLAUDE.md. Ejecuta desde la raíz del template." >&2; exit 1; }

MODE="$MODE" FORCE="$FORCE" python3 - <<'PYEOF'
import os, re, sys, pathlib

MODE  = os.environ["MODE"]
FORCE = os.environ["FORCE"] == "yes"

SRC_DIR = pathlib.Path(".claude/commands")
OUT_DIR = pathlib.Path(".cursor/rules")
GOB_FILE = OUT_DIR / "00-gobernanza.mdc"
GOB_SHORT = "`00-gobernanza`"
GOB_PATH  = "`.cursor/rules/00-gobernanza.mdc`"

CMDS = sorted(p.stem for p in SRC_DIR.glob("*.md"))
SLASH = re.compile(r'(?<![\w/])/(' + "|".join(map(re.escape, CMDS)) + r')\b')

# ── Casos que no son transformación mecánica ─────────────────────────────────
# Todo lo demás sale de las reglas genéricas de abajo. Si agregas un comando
# nuevo con una construcción que el generador no entiende, la verificación
# final falla y te dice el archivo y la línea.
OVERRIDES = {
    "git-setup.md": [
        # Comandos de shell reales: aquí CLAUDE.md no es una referencia, es un
        # argumento de `git add`, y en Cursor el equivalente es .cursor/.
        ("git add CLAUDE.md .claude/ .gitignore README.md 2>/dev/null || git add CLAUDE.md .claude/",
         "git add .cursor/ .gitignore README.md 2>/dev/null || git add .cursor/"),
    ],
    "discovery.md": [
        ("[copia de CLAUDE.md]",
         '[copia de la sección "Tipo de proyecto" de ' + GOB_SHORT + "]"),
        # Instrucciones de escritura: conviene la ruta completa, no el nombre corto.
        ('Actualiza `CLAUDE.md` directamente — la sección "Tipo de proyecto" — con:',
         "Actualiza " + GOB_PATH + ' directamente — la sección "Tipo de proyecto" — con:'),
        ('2. Actualiza la sección **"Norte del proyecto"** de `CLAUDE.md`, reemplazando el `[pendiente]`.',
         '2. Actualiza la sección **"Norte del proyecto"** de ' + GOB_PATH + ", reemplazando el `[pendiente]`."),
    ],
    "architect.md": [
        ('5. **Actualiza `CLAUDE.md`** — solo las secciones "Stack del proyecto" y "Comandos del proyecto".',
         "5. **Actualiza " + GOB_PATH + '** — solo las secciones "Stack del proyecto" y "Comandos del proyecto".'),
    ],
}

# ── Transformaciones de CLAUDE.md → 00-gobernanza.mdc ────────────────────────
GOB_OVERRIDES = [
    ("# Gobernanza del proyecto\n\nEste archivo define cómo trabaja Claude Code en este repositorio.\n**Lee este archivo completo antes de cualquier acción.**",
     "# Gobernanza del proyecto\n\nEsta regla define cómo se trabaja en este repositorio. Se aplica siempre, en cada request.\n**Es la constitución del proyecto: ninguna otra regla la contradice.**"),
    # En Claude Code un hook lee protected.txt. En Cursor no hay hook, así que
    # la lista tiene que estar donde el agente la vea sí o sí.
    ("1. **Nunca modifiques archivos fuera del scope que te pedí.** Si necesitas tocar algo fuera, pregúntame primero y explica por qué. Lista de archivos protegidos en `.claude/protected.txt`.",
     "1. **Nunca modifiques archivos fuera del scope que te pedí.** Si necesitas tocar algo fuera, "
     "pregúntame primero y explica por qué. Archivos protegidos, que nunca tocas sin permiso explícito:\n"
     "   `.env`, `.env.*`, `*.pem`, `*.key`, `secrets/**`, `.git/**`, `.github/workflows/**`,\n"
     "   esta misma regla (" + GOB_SHORT + "), `docs/adr/**`, `docs/contracts/**`, `LICENSE`."),
    ('Modificar la sección "Norte del proyecto" requiere mi aprobación explícita, igual que cualquier archivo en `.claude/protected.txt`.',
     'Modificar la sección "Norte del proyecto" requiere mi aprobación explícita, igual que cualquier archivo protegido de la regla 1.'),
    ("Cada fase tiene un slash command con restricciones claras. **Fuera de un comando, modo consulta: respondes preguntas, no modificas nada.**",
     "Cada fase es una regla que el usuario invoca con `@`, con restricciones claras. **Fuera de una fase, modo consulta: respondes preguntas, no modificas nada.**"),
    ("| Fase | Comando | Qué haces |", "| Fase | Regla | Qué haces |"),
    ("Los slash commands (especialmente `@implement`) usan", "Las reglas de fase (especialmente `@implement`) usan"),
]

ENFORCEMENT = """
## Qué se hace cumplir con código y qué depende de ti

Esta distinción es importante y no puedes ignorarla.

**Se hace cumplir mecánicamente** (hooks de Git instalados por `@git-setup`, funcionan igual en
cualquier editor):

- `commit-msg` — rechaza el commit si el asunto no sigue el formato convencional.
- `pre-commit` — bloquea `.env`, `*.db`, `node_modules/` y demás archivos prohibidos; corre lint y type-check.
- `pre-push` — corre los tests y advierte si el push va directo a `main`.

**Depende enteramente de que tú las respetes** (no hay nada que te lo impida):

- Las 11 reglas duras de arriba.
- La lista de archivos protegidos de la regla 1.
- No ejecutar comandos destructivos sin que el usuario escriba "confirmo".
- Parar y preguntar en vez de adivinar.

En Claude Code estas cuatro las bloquea un hook del editor. Aquí no existe ese hook: si las rompes,
nada te detiene y el usuario se entera cuando ya está hecho. Trátalas como si el bloqueo existiera.

---

"""

# ── Helpers ──────────────────────────────────────────────────────────────────

def split_front(text, origin):
    m = re.match(r'^---\n(.*?)\n---\n', text, flags=re.S)
    if not m:
        die(f"{origin}: no tiene frontmatter YAML.")
    return m.group(1), text[m.end():]

def front_field(front, key):
    for line in front.splitlines():
        if line.startswith(key + ":"):
            return line[len(key) + 1:].strip()
    return ""

ERRORS = []
def die(msg):
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)

def common_transforms(body, name):
    body = SLASH.sub(r'@\1', body)
    body = body.replace("`CLAUDE.md`", GOB_SHORT)
    body = re.sub(r'(?<![`\w])CLAUDE\.md(?![`\w])', GOB_SHORT, body)
    body = body.replace(".claude/commands/", ".cursor/rules/")
    return body

FORBIDDEN = [
    (re.compile(r'(?<![\w/])/(' + "|".join(map(re.escape, CMDS)) + r')\b'), "slash command de Claude Code"),
    (re.compile(r'CLAUDE\.md'),      "referencia a CLAUDE.md"),
    (re.compile(r'\.claude/'),       "ruta .claude/"),
    (re.compile(r'\.cursorrules'),   "referencia a .cursorrules (el template no crea ese archivo)"),
    (re.compile(r'\$ARGUMENTS'),     "$ARGUMENTS (Cursor no lo sustituye)"),
    (re.compile(r'^argument-hint:', re.M), "argument-hint (Cursor lo ignora)"),
]

def verify(name, text):
    problems = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for pattern, label in FORBIDDEN:
            if pattern.search(line):
                problems.append(f"    {name}:{lineno}: {label}\n      {line.strip()[:100]}")
    return problems

# ── Generar las reglas de fase ───────────────────────────────────────────────

generated = {}

for src in sorted(SRC_DIR.glob("*.md")):
    name = src.stem
    front, body = split_front(src.read_text(encoding="utf-8"), str(src))

    for old, new in OVERRIDES.get(src.name, []):
        if old not in body:
            die(f"{src}: el override esperado ya no aparece en la fuente.\n   {old[:80]}")
        body = body.replace(old, new)

    # $ARGUMENTS no existe en Cursor. El texto del argument-hint se funde en la
    # línea, que es donde de verdad le sirve al agente.
    if "$ARGUMENTS" in body:
        hint = front_field(front, "argument-hint")
        detail = hint[1:-1].strip() if hint.startswith("[") and hint.endswith("]") else ""
        line = f"**lo que el usuario haya escrito junto a `@{name}`**"
        if detail:
            line += f" — {detail}"
        line += ".\nSi no lo indicó, pregúntaselo antes de continuar."
        body = body.replace("**$ARGUMENTS**", line).replace("$ARGUMENTS", line)

    body = common_transforms(body, name)

    desc = front_field(front, "description") or f"Fase {name}."
    if "@" + name not in desc:
        desc = f"{desc} Úsalo con @{name}"
    out = f"---\ndescription: {desc}\nglobs:\nalwaysApply: false\n---\n\n{body.strip()}\n"
    generated[OUT_DIR / f"{name}.mdc"] = out

# ── Generar 00-gobernanza.mdc ────────────────────────────────────────────────

gob = pathlib.Path("CLAUDE.md").read_text(encoding="utf-8")
gob = SLASH.sub(r'@\1', gob)
gob = gob.replace(".claude/commands/", ".cursor/rules/")
for old, new in GOB_OVERRIDES:
    if old not in gob:
        die(f"CLAUDE.md: el override esperado ya no aparece.\n   {old[:80]}")
    gob = gob.replace(old, new)

marker = "\n## Uso del grafo de graphify"
if marker not in gob:
    die("CLAUDE.md: no encuentro la sección 'Uso del grafo de graphify' para insertar el bloque de enforcement.")
gob = gob.replace(marker, "\n" + ENFORCEMENT.strip() + marker, 1)

gob_out = ("---\n"
           "description: Gobernanza del proyecto — norte, reglas duras, fases y estrategia de Git. Siempre activa.\n"
           "globs:\nalwaysApply: true\n---\n\n" + gob.strip() + "\n")

# El norte lo escribe @discovery en el proyecto del usuario. Si ya está lleno,
# regenerar desde el CLAUDE.md del template lo borraría.
skip_gob = False
if GOB_FILE.exists() and not FORCE:
    current = GOB_FILE.read_text(encoding="utf-8")
    m = re.search(r'\*\*Este sistema existe para:\*\*(.*)', current)
    if m and "[pendiente" not in m.group(1):
        skip_gob = True
if not skip_gob:
    generated[GOB_FILE] = gob_out

# ── Verificar ────────────────────────────────────────────────────────────────

problems = []
for path, text in sorted(generated.items()):
    problems += verify(path.name, text)

if problems:
    print("❌ El resultado todavía contiene construcciones que no existen en Cursor:\n")
    print("\n".join(problems))
    print("\n   Agrega el caso a OVERRIDES en generate-cursor-rules.sh, o corrige la fuente.")
    sys.exit(1)

# ── Escribir o comparar ──────────────────────────────────────────────────────

if MODE == "check":
    stale = [p for p, t in sorted(generated.items())
             if not p.exists() or p.read_text(encoding="utf-8") != t]
    if stale:
        print("❌ Las reglas de Cursor están desactualizadas respecto a .claude/commands/:\n")
        for p in stale:
            print(f"    {p}")
        print("\n   Regenera con: bash generate-cursor-rules.sh")
        sys.exit(1)
    extra = sorted(p.name for p in OUT_DIR.glob("*.mdc") if p not in generated and p != GOB_FILE)
    if extra:
        print("⚠️  Reglas en .cursor/rules/ sin fuente en .claude/commands/: " + ", ".join(extra))
    print(f"✅ Las {len(generated)} reglas de Cursor están al día.")
    sys.exit(0)

OUT_DIR.mkdir(parents=True, exist_ok=True)
changed = 0
for path, text in sorted(generated.items()):
    before = path.read_text(encoding="utf-8") if path.exists() else None
    if before != text:
        path.write_text(text, encoding="utf-8")
        print(f"  ✓ {path}")
        changed += 1
    else:
        print(f"  · {path} (sin cambios)")

if skip_gob:
    print(f"\n  ↩︎  {GOB_FILE} preservado: tiene un norte definido.")
    print("      Para regenerarlo de todas formas: bash generate-cursor-rules.sh --force")

print(f"\n✅ {len(generated)} reglas generadas desde .claude/commands/ y CLAUDE.md ({changed} con cambios).")
PYEOF

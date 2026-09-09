#!/usr/bin/env python3
"""Revisor de seguridad de migraciones de base de datos.

El incidente clásico de despliegue no es un bug de lógica: es una migración que
borra una columna mientras la versión anterior de la aplicación sigue corriendo.
Durante un despliegue las dos versiones conviven — minutos en un rolling update,
horas si hay que revertir. Una migración que solo es compatible con el código nuevo
rompe en esa ventana, y rompe en producción con datos reales.

La regla es **expand / migrate / contract**:

  1. EXPAND   — agregar lo nuevo, nullable y con default. El código viejo lo ignora.
  2. MIGRATE  — backfill y desplegar el código nuevo. Las dos versiones funcionan.
  3. CONTRACT — quitar lo viejo, en un release POSTERIOR, cuando ya nada lo usa.

Este script no puede saber en qué fase estás: lo que hace es detectar las
operaciones que solo son seguras en la fase 3 y exigir que lo declares.

Uso:
    python3 .workflow/check-migrations.py              # migraciones del diff vs base
    python3 .workflow/check-migrations.py --all        # todas las del repo
    python3 .workflow/check-migrations.py --base main

Para declarar una operación destructiva como deliberada, ponla en el propio archivo
de migración, en un comentario:

    # expand-contract: contract — la columna dejó de usarse en v1.4.0, desplegado 2026-01-10
    # irreversible: la tabla de auditoría no se puede reconstruir; backup verificado antes
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# ── Qué archivos son migraciones ─────────────────────────────────────────────

PATRONES_RUTA = [
    re.compile(r"(^|/)migrations?/"),      # alembic, django, prisma, typeorm
    re.compile(r"(^|/)migrate/"),          # rails: db/migrate/
    re.compile(r"(^|/)V\d+__.*\.sql$"),    # flyway
    re.compile(r"(^|/)db/changelog/"),     # liquibase
]
EXTENSIONES = {".sql", ".py", ".rb", ".js", ".ts", ".go", ".xml"}


def es_migracion(ruta):
    p = ruta.replace("\\", "/")
    if Path(p).suffix not in EXTENSIONES:
        return False
    return any(rx.search(p) for rx in PATRONES_RUTA)


# ── Operaciones que solo son seguras en la fase de contracción ───────────────
#
# (regex, severidad, qué rompe)

DESTRUCTIVAS = [
    (re.compile(r"\bDROP\s+TABLE\b", re.I), "blocker",
     "elimina una tabla: el código anterior que aún la consulta falla durante el despliegue"),
    (re.compile(r"\bDROP\s+COLUMN\b", re.I), "blocker",
     "elimina una columna: el código anterior que la selecciona o escribe falla"),
    (re.compile(r"\bop\.drop_table\b"), "blocker",
     "elimina una tabla (alembic)"),
    (re.compile(r"\bop\.drop_column\b"), "blocker",
     "elimina una columna (alembic)"),
    (re.compile(r"\bmigrations\.DeleteModel\b"), "blocker",
     "elimina un modelo (django)"),
    (re.compile(r"\bmigrations\.RemoveField\b"), "blocker",
     "elimina un campo (django)"),
    (re.compile(r"\bRENAME\s+(COLUMN|TO)\b", re.I), "blocker",
     "renombrar no es compatible hacia atrás: para el código anterior la columna desapareció. "
     "Se hace en dos pasos — agregar la nueva, backfill, y quitar la vieja en otro release"),
    (re.compile(r"\bmigrations\.RenameField\b|\bop\.alter_column\([^)]*new_column_name"), "blocker",
     "renombra una columna: no es compatible hacia atrás"),
    (re.compile(r"\bSET\s+NOT\s+NULL\b", re.I), "blocker",
     "poner NOT NULL sobre una columna existente rompe los INSERT del código anterior, "
     "que no manda ese campo. Requiere default o dos fases"),
    (re.compile(r"nullable\s*=\s*False", re.I), "important",
     "columna no nullable: si es una columna existente, rompe los INSERT del código anterior. "
     "Si es nueva, necesita server_default para las filas que ya existen"),
    (re.compile(r"\bALTER\s+COLUMN\b.*\bTYPE\b", re.I), "important",
     "cambiar el tipo de una columna puede reescribir la tabla entera (lock largo) y romper "
     "la lectura del código anterior"),
    (re.compile(r"\bTRUN" + r"CATE\b", re.I), "blocker",
     "borra todas las filas de la tabla"),
    (re.compile(r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", re.I | re.S), "blocker",
     "DELETE sin WHERE: borra la tabla completa"),
    (re.compile(r"\bDROP\s+(INDEX|CONSTRAINT)\b", re.I), "important",
     "quitar un índice o constraint puede degradar consultas del código anterior o permitir "
     "datos que este esperaba imposibles"),
]

# Operaciones caras que pueden bloquear la tabla en producción
BLOQUEANTES = [
    (re.compile(r"\bCREATE\s+INDEX\b(?!\s+CONCURRENTLY)", re.I), "important",
     "CREATE INDEX sin CONCURRENTLY bloquea escrituras en la tabla mientras se construye. "
     "En una tabla grande eso es una caída"),
    (re.compile(r"\bUPDATE\s+\w+\s+SET\b(?!.*\bWHERE\b)", re.I | re.S), "important",
     "UPDATE masivo sin WHERE: en una tabla grande mantiene un lock largo. Hazlo por lotes"),
]

# ── Declaraciones que el autor puede poner en el archivo ─────────────────────

MARCA_CONTRACT = re.compile(r"expand-contract\s*:\s*contract\b", re.I)
MARCA_IRREVERSIBLE = re.compile(r"irreversible\s*:\s*\S+", re.I)


def tiene_justificacion(texto, marca):
    """La marca vale solo si viene con una razón detrás, no suelta."""
    m = marca.search(texto)
    if not m:
        return False
    resto = texto[m.end():m.end() + 200].split("\n")[0].strip(" —-:")
    return len(resto) >= 15


# ── Solo el camino de ida ────────────────────────────────────────────────────

def parte_hacia_adelante(ruta, texto):
    """Devuelve solo la parte que se aplica al migrar.

    Un `drop_column` dentro de `downgrade()` es correcto: es cómo se deshace un
    `add_column`. Escanear el archivo entero marcaba como peligrosa toda migración
    bien escrita.
    """
    p = str(ruta)

    if p.endswith(".py"):
        m = re.search(r"def\s+upgrade\s*\([^)]*\)\s*:(.*?)(?=\ndef\s|\Z)", texto, re.S)
        if m:
            return m.group(1)
        # django: la lista `operations` es el camino de ida
        m = re.search(r"operations\s*=\s*\[(.*?)\n\s*\]", texto, re.S)
        if m:
            return m.group(1)

    if p.endswith(".sql"):
        m = re.search(r"--\s*(down|rollback|undo)\b", texto, re.I)
        if m:
            return texto[:m.start()]

    return texto


# ── Reversibilidad ───────────────────────────────────────────────────────────

def revisar_reversibilidad(ruta, texto):
    """¿Se puede deshacer esta migración? Devuelve un problema o None."""
    p = str(ruta)

    if p.endswith(".py") and "def upgrade" in texto:  # alembic
        m = re.search(r"def\s+downgrade\s*\([^)]*\)\s*:(.*?)(?=\ndef\s|\Z)", texto, re.S)
        if not m:
            return "no tiene función downgrade()"
        cuerpo = re.sub(r"#.*|\"\"\".*?\"\"\"|'''.*?'''", "", m.group(1), flags=re.S).strip()
        if not cuerpo or cuerpo in ("pass", "..."):
            return "downgrade() está vacío: la migración no se puede revertir"
        if "NotImplementedError" in cuerpo or "raise" == cuerpo.split()[0]:
            return "downgrade() lanza una excepción: la migración no se puede revertir"

    if p.endswith(".py") and "migrations.RunPython" in texto:  # django
        if not re.search(r"RunPython\s*\([^)]*(reverse_code|noop)", texto, re.S):
            return "RunPython sin reverse_code: la migración de datos no se puede revertir"

    if p.endswith(".sql"):
        tiene_down = (
            re.search(r"--\s*(down|rollback|undo)\b", texto, re.I)
            or Path(p).with_suffix("").name.endswith(".up")
            or (Path(p).parent / (Path(p).stem + ".down.sql")).exists()
            or "down.sql" in p
        )
        if not tiene_down:
            return "no encuentro el SQL de rollback (una sección '-- down' o un archivo .down.sql)"

    return None


# ── Recolección de archivos ──────────────────────────────────────────────────

def git(*args):
    return subprocess.run(["git", *args], capture_output=True, text=True).stdout


def base_por_defecto():
    for ref in ("origin/develop", "develop", "origin/main", "main"):
        if subprocess.run(["git", "rev-parse", "--verify", ref],
                          capture_output=True).returncode == 0:
            return ref
    return None


def archivos_a_revisar(args):
    if args.all:
        return [r for r in git("ls-files").splitlines() if es_migracion(r)]

    base = args.base or base_por_defecto()
    if not base:
        print("⚠️  Sin rama base para comparar; revisando todas las migraciones.")
        return [r for r in git("ls-files").splitlines() if es_migracion(r)]

    diff = git("diff", "--name-only", "--diff-filter=ACM", f"{base}...HEAD").splitlines()
    diff += git("diff", "--name-only", "--diff-filter=ACM").splitlines()
    diff += git("diff", "--name-only", "--diff-filter=ACM", "--cached").splitlines()
    return sorted({r for r in diff if es_migracion(r)})


# ── Principal ────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="revisar todas las migraciones del repo")
    ap.add_argument("--base", help="rama o commit contra el que comparar")
    ap.add_argument("--strict", action="store_true",
                    help="fallar también con hallazgos 'important' (usar en CI de main)")
    args = ap.parse_args()

    rutas = archivos_a_revisar(args)
    if not rutas:
        print("✓ Sin migraciones nuevas o modificadas.")
        return 0

    print(f"🗄️  Revisando {len(rutas)} migración(es)...\n")

    bloqueantes, importantes = [], []

    for ruta in rutas:
        p = Path(ruta)
        try:
            texto = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        declarado_contract = tiene_justificacion(texto, MARCA_CONTRACT)
        declarado_irrev = tiene_justificacion(texto, MARCA_IRREVERSIBLE)
        hallazgos = []

        adelante = parte_hacia_adelante(p, texto)
        desfase = texto.find(adelante) if adelante is not texto else 0
        desfase = max(desfase, 0)

        for rx, sev, motivo in DESTRUCTIVAS + BLOQUEANTES:
            m = rx.search(adelante)
            if not m:
                continue
            if declarado_contract and sev == "blocker":
                continue  # el autor declaró que es la fase de contracción, con razón
            linea = texto[:desfase + m.start()].count("\n") + 1
            hallazgos.append((sev, linea, m.group(0).strip()[:40], motivo))

        problema = revisar_reversibilidad(p, texto)
        if problema and not declarado_irrev:
            hallazgos.append(("important", 0, "reversibilidad", problema))

        if not hallazgos:
            marca = " (contracción declarada)" if declarado_contract else ""
            print(f"  ✓ {ruta}{marca}")
            continue

        print(f"  ⚠️  {ruta}")
        for sev, linea, frag, motivo in hallazgos:
            icono = "🔴" if sev == "blocker" else "🟠"
            ubic = f":{linea}" if linea else ""
            print(f"     {icono} {frag}{ubic}")
            print(f"        {motivo}")
            (bloqueantes if sev == "blocker" else importantes).append((ruta, frag))
        print()

    print("─" * 60)
    print(f"  {len(bloqueantes)} bloqueante(s), {len(importantes)} importante(s)")

    if bloqueantes or (args.strict and importantes):
        print("""
Estas operaciones solo son seguras en la fase de CONTRACCIÓN, con el código
anterior ya fuera de servicio. Si es tu caso, decláralo en el propio archivo:

  # expand-contract: contract — [en qué release dejó de usarse y cuándo se desplegó]
  # irreversible: [por qué, y qué respaldo existe]

Si no es tu caso, pártela en dos releases: expandir ahora, contraer después.""")
        return 1

    if importantes:
        print("\n⚠️  Revisa los importantes antes de desplegar. No bloquean, pero cuestan caro.")
    else:
        print("  ✓ Sin operaciones peligrosas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

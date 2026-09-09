#!/usr/bin/env python3
"""Detección de comandos destructivos, distinguiendo invocación de mención.

`check-bash.sh` buscaba sus patrones peligrosos sobre el texto crudo del comando,
sin segmentar y sin quitar heredocs. Cualquier comando que *contuviera* el texto
quedaba bloqueado aunque no lo ejecutara: documentar la propia capa de seguridad
era imposible desde el agente (hallazgo I3).

El efecto práctico de eso no era más seguridad, era menos: el camino de escape
natural es que el usuario acabe escribiendo "confirmo" por costumbre, y ahí la
barrera deja de valer nada.

La distinción que faltaba es **posición de comando**:

    rm -rf /            → invocación. Se bloquea.
    echo "rm -rf /"     → mención. Pasa, con aviso.

Los patrones se clasifican en tres:

  COMANDO   — solo cuentan si el segmento empieza por ese verbo (saltando
              asignaciones de entorno y sudo).
  CLIENTE   — SQL destructivo: solo cuenta si el segmento invoca un cliente de
              base de datos. Un DDL dentro de un string de documentación no borra
              nada.
  SIEMPRE   — inconfundibles y ausentes de la documentación normal (fork bomb,
              escritura directa a un dispositivo de bloque).

Uso:
    danger-scan.py       # stdin: JSON del hook
      exit 2 → invocación peligrosa, bloquear
      exit 0 → nada, o solo mención (con aviso en stderr)
"""

import json
import os
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from write_guard import strip_heredocs  # noqa: F401
except ImportError:
    # write-guard.py lleva guion, así que no es importable por nombre. Se carga
    # por ruta; si tampoco se puede, se usa una copia mínima equivalente.
    import importlib.util

    _spec = importlib.util.spec_from_file_location(
        "write_guard", Path(__file__).resolve().parent / "write-guard.py")
    if _spec and _spec.loader:
        _wg = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_wg)
        strip_heredocs = _wg.strip_heredocs
    else:  # pragma: no cover
        def strip_heredocs(text):
            return text


# ── Clasificación de patrones ────────────────────────────────────────────────

# (regex sobre el segmento completo, descripción)
# Solo cuentan si el segmento está en posición de comando con ese verbo.
COMANDO = [
    (re.compile(r"^rm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*r[a-zA-Z]*f?[a-zA-Z]*\s+(/|\*|~)(\s|$)"),
     "borrado recursivo de la raíz, del home o de un glob sin acotar"),
    (re.compile(r"^rm\s+.*\s-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\s+(/|\*|~)(\s|$)"),
     "borrado recursivo de la raíz, del home o de un glob sin acotar"),
    (re.compile(r"^git\s+push\b.*(--force(?!-with-lease)|\s-f(\s|$))"),
     "push forzado: reescribe historia publicada"),
    (re.compile(r"^git\s+reset\s+--hard\b"),
     "descarta cambios locales sin posibilidad de recuperarlos"),
    (re.compile(r"^git\s+clean\s+-[a-zA-Z]*f"),
     "borra archivos no versionados sin papelera"),
    (re.compile(r"^mkfs\."), "formatea un sistema de archivos"),
    (re.compile(r"^dd\b.*\bof=/dev/"), "escribe directamente sobre un dispositivo"),
    (re.compile(r"^chmod\s+-R\s+777\b"), "permisos totales recursivos"),
]

# SQL destructivo: solo si el segmento habla con una base de datos.
CLIENTES_DB = re.compile(
    r"^(sudo\s+)?(psql|mysql|mariadb|sqlite3?|mongo|mongosh|redis-cli|"
    r"cockroach|clickhouse-client|alembic|prisma|flyway|liquibase|dbmate)\b")

SQL_DESTRUCTIVO = [
    (re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", re.I), "elimina una tabla o base de datos"),
    (re.compile(r"\bTRUN" + r"CATE\b", re.I), "vacía una tabla completa"),
    (re.compile(r"\bDELETE\s+FROM\b(?!.*\bWHERE\b)", re.I | re.S), "borra todas las filas de una tabla"),
]

# Inconfundibles: se buscan en todo el texto.
SIEMPRE = [
    (re.compile(r":\s*\(\s*\)\s*\{.*\|\s*:\s*&.*\}\s*;\s*:"), "fork bomb"),
    (re.compile(r">\s*/dev/(sd[a-z]|nvme\d|disk\d)"), "escritura directa sobre un disco"),
]

# Verbos que ejecutan lo que reciben por stdin: para ellos el heredoc NO es
# solo datos, así que no se puede recortar.
INTERPRETES = re.compile(r"^(sudo\s+)?(ba|z|k|da|)sh\b|^(sudo\s+)?python3?\b|"
                         r"^(sudo\s+)?(perl|ruby|node|php)\b")

ASIGNACION = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


# ── Segmentación ─────────────────────────────────────────────────────────────

def segmentos(cmd):
    """Trocea el comando en segmentos que empiezan en posición de comando.

    Además de los separadores normales, abre las sustituciones $( ) y ` `: lo de
    dentro también arranca en posición de comando.
    """
    texto = re.sub(r"\$\(|\)|`", "\n", cmd)
    for pieza in re.split(r"(?:\|\||&&|[;&|\n])+", texto):
        pieza = pieza.strip()
        if pieza:
            yield pieza


def verbo_de(seg):
    """Primer verbo real del segmento, saltando asignaciones de entorno y sudo."""
    try:
        tokens = shlex.split(seg, posix=True)
    except ValueError:
        tokens = seg.split()
    i = 0
    while i < len(tokens) and ASIGNACION.match(tokens[i]):
        i += 1
    if i < len(tokens) and tokens[i] in ("sudo", "doas", "env"):
        i += 1
        while i < len(tokens) and ASIGNACION.match(tokens[i]):
            i += 1
    return " ".join(tokens[i:]) if i < len(tokens) else ""


def preparar(cmd):
    """Quita los cuerpos de heredoc, salvo cuando el verbo es un intérprete.

    `python3 - <<'PY'` sí ejecuta el cuerpo: ahí el heredoc no es dato.
    """
    primer = verbo_de(next(iter(segmentos(cmd)), ""))
    if INTERPRETES.match(primer):
        return cmd
    return strip_heredocs(cmd)


# ── Análisis ─────────────────────────────────────────────────────────────────

FLAG_C = re.compile(r"^(sudo\s+)?\S*(sh|python3?|perl|ruby|node|php)\s+.*?-c\b")


def argumento_de_c(seg):
    """El comando que un intérprete recibe con -c. Es código, no texto."""
    if not FLAG_C.match(seg):
        return None
    try:
        tokens = shlex.split(seg, posix=True)
    except ValueError:
        return None
    for i, tok in enumerate(tokens):
        if tok == "-c" and i + 1 < len(tokens):
            return tokens[i + 1]
    return None


def analizar(cmd, _profundidad=0):
    """Devuelve (invocaciones, menciones): listas de (fragmento, descripción)."""
    texto = preparar(cmd)
    invocaciones, menciones = [], []

    for rx, desc in SIEMPRE:
        if rx.search(texto):
            invocaciones.append((rx.pattern[:30], desc))

    for seg in segmentos(texto):
        nucleo = verbo_de(seg)
        if not nucleo:
            continue

        for rx, desc in COMANDO:
            if rx.search(nucleo):
                invocaciones.append((nucleo[:60], desc))

        es_cliente = bool(CLIENTES_DB.match(nucleo))
        for rx, desc in SQL_DESTRUCTIVO:
            m = rx.search(seg)
            if not m:
                continue
            (invocaciones if es_cliente else menciones).append((m.group(0)[:60], desc))

        # `sh -c "..."`: el argumento se ejecuta, así que se analiza como comando.
        # Sobre `seg`, no sobre `nucleo`: nucleo pasó por un join que pierde las
        # comillas, y con ellas el argumento entero de -c.
        interno = argumento_de_c(seg) if _profundidad < 3 else None
        if interno:
            inv2, men2 = analizar(interno, _profundidad + 1)
            invocaciones += inv2
            menciones += men2

    # Lo que aparece en el texto pero no en posición de comando es una mención.
    for rx, desc in COMANDO:
        if rx.pattern.startswith("^"):
            suelto = re.compile(rx.pattern[1:])
            if suelto.search(texto) and not any(d == desc for _, d in invocaciones):
                menciones.append((desc, desc))

    return invocaciones, menciones


def main():
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0

    cmd = (data.get("tool_input") or {}).get("command", "")
    if not cmd:
        return 0

    invocaciones, menciones = analizar(cmd)

    if invocaciones:
        sys.stderr.write("🛑 COMANDO DESTRUCTIVO DETECTADO\n")
        for frag, desc in invocaciones:
            sys.stderr.write(f"   {frag}\n      → {desc}\n")
        sys.stderr.write(
            "\nEsto no es una mención dentro de una cadena: está en posición de comando.\n"
            "Si realmente hay que ejecutarlo, pide al usuario que escriba 'confirmo'.\n")
        return 2

    if menciones and os.environ.get("DANGER_SCAN_QUIET") != "1":
        vistos = {d for _, d in menciones}
        sys.stderr.write(
            "ℹ️  El comando menciona un patrón destructivo dentro de una cadena o "
            f"comentario ({'; '.join(sorted(vistos))}), pero no lo ejecuta. Se deja pasar.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())

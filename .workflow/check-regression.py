#!/usr/bin/env python3
"""Prueba que un test falla SIN el arreglo.

Un test escrito después del fix, sobre el código ya arreglado, pasa siempre. No
demuestra nada: no habría atrapado el bug. Es el fallo silencioso más común al
cerrar hallazgos, porque la suite queda verde y nadie sospecha.

Este script lo comprueba de la única forma que vale: monta el árbol del commit
PADRE del arreglo en un worktree aparte, le trae encima solo los archivos de test
del commit del arreglo, y corre el test ahí. Si el test pasa sobre el código sin
arreglar, el test no sirve.

Los archivos de test se traen todos los que el commit tocó y parezcan test (no
solo el que se nombra) porque un test nuevo suele venir con su `conftest.py` o su
fixture, y sin ellos el test no arranca por el motivo equivocado. Si un patrón de
test llegara a coincidir con código de producción, el arreglo viajaría al worktree
y el test pasaría: se reporta 'no-prueba-nada'. Falla hacia el lado seguro.

Códigos de salida:
    0  regresión confirmada — el test falla sin el arreglo
    1  el test pasa sin el arreglo: no demuestra nada
    2  no se pudo verificar (falta la herramienta, el comando no corre, etc.)

Uso:
    python3 .workflow/check-regression.py --commit abc1234 --test tests/test_api.py::test_put
    python3 .workflow/check-regression.py --commit abc1234 --test t.py --cmd "pytest -x" --json
"""

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")

# Directorios que se enlazan al worktree si existen: sin ellos el test falla por
# dependencias ausentes, que es un 'no-verificada', no un 'no-prueba-nada'.
DEPS = ("node_modules", ".venv", "venv", "vendor", "target/debug/deps")

CONFIRMADA = "confirmada"
NO_PRUEBA = "no-prueba-nada"
NO_VERIFICADA = "no-verificada"
NO_APLICABLE = "no-aplicable"

# Diagnósticos con los que un runner dice "no llegué a correr el test": el árbol sin
# el arreglo no compila, no resuelve un import, o no encontró ningún caso. Eso NO es
# "el test falló", y confundirlo es el falso verde que este script existe para evitar.
# Importa sobre todo en el caso más común de todos — un test nuevo sobre una función
# nueva: sin el arreglo el símbolo no existe y el runner revienta al cargar el archivo.
# Son cadenas de diagnóstico, no texto de aserción, para no degradar confirmaciones
# legítimas: un test que imprime "esperaba 3, obtuve 1" no coincide con ninguna.
SUITE_ROTA = re.compile(
    r"ModuleNotFoundError|ImportError|ReferenceError|SyntaxError"
    r"|Cannot find module|Failed to load|Failed to resolve import"
    r"|does not provide an export|is not exported"
    r"|error TS\d+|build failed|compilation error"
    r"|No test files found|no tests? found",
    re.I,
)

# Código de salida que cada runner usa para "los tests fallaron", por extensión del
# archivo de test. Fuera de esta tabla no se afirma nada: ver interpretar().
FALLO_DE_TEST = {".go": 1, ".rs": 101}


def git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def es_test(ruta):
    p = ruta.replace("\\", "/")
    base = p.rsplit("/", 1)[-1]
    if any(d in f"/{p}" for d in ("/tests/", "/test/", "/__tests__/", "/spec/")):
        return True
    if base in ("conftest.py",):
        return True
    if base.startswith(("test_", "test-")):
        return True
    return base.endswith(("_test.py", "_test.go", ".test.ts", ".test.tsx", ".test.js",
                          ".spec.ts", ".spec.tsx", ".spec.js", "_test.exs", "Test.java"))


def comando_para(ruta, spec):
    """Comando por defecto según el tipo de test. Best-effort: si no hay mapeo, se pide --cmd."""
    if ruta.endswith(".py"):
        binario = "pytest" if shutil.which("pytest") else None
        base = [binario] if binario else [sys.executable, "-m", "pytest"]
        return [*base, spec, "-x", "-q"]
    if ruta.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs")):
        return ["npm", "test", "--", ruta]
    if ruta.endswith(".go"):
        if "::" in spec:
            return ["go", "test", "./...", "-run", spec.split("::")[-1]]
        return ["go", "test", "./..."]
    if ruta.endswith(".rs"):
        return ["cargo", "test"] + ([spec.split("::")[-1]] if "::" in spec else [])
    if ruta.endswith((".sh", ".bash")):
        return ["bash", ruta]
    return None


def interpretar(ruta, code, salida=""):
    """Traduce el código de salida del runner a un resultado, con su razón.

    Ante la duda devuelve NO_VERIFICADA, nunca CONFIRMADA. Un 'no-verificada' de más
    cuesta que el hallazgo cierre como 'declarado' y se note; un 'confirmada' de más
    certifica una regresión que nadie comprobó, que es justo lo que este script existe
    para impedir. Hasta 2026-09-11 el default fuera de pytest era CONFIRMADA: cualquier
    salida distinta de 0 y 127 se daba por buena, admitiendo en el propio mensaje que no
    se podía distinguir 'test falló' de 'suite rota'. Eso invertía el propósito del
    chequeo (hallazgo B1, detectado con vitest saliendo 254 en musicos).
    """
    if code == 0:
        return NO_PRUEBA, "el test pasó sobre el código sin arreglar"
    if code == 127:
        return NO_VERIFICADA, "el runner no está instalado (exit 127)"

    if ruta.endswith(".py"):
        # pytest: 1 = tests fallaron, 2/3/4 = error de uso o interrupción, 5 = no recolectó nada.
        # Su tabla es precisa, así que no se le aplica SUITE_ROTA: un test que legítimamente
        # afirma que se levanta un ImportError imprimiría esa cadena sin estar rota la suite.
        if code == 1:
            return CONFIRMADA, "el test falló sobre el código sin arreglar"
        if code == 5:
            return NO_VERIFICADA, "pytest no recolectó el test en el árbol sin el arreglo"
        return NO_VERIFICADA, f"pytest terminó con error de ejecución (exit {code})"

    # Fuera de pytest el código de salida solo distingue si el runner respeta la
    # convención. Antes de mirarlo, el veredicto del propio runner sobre sí mismo.
    roto = SUITE_ROTA.search(salida or "")
    if roto:
        return NO_VERIFICADA, (
            f"el runner no llegó a correr el test en el árbol sin el arreglo "
            f"(dice '{roto.group(0)}'): sin el arreglo el símbolo bajo prueba no existe "
            f"y el archivo no carga. Eso no demuestra regresión, demuestra que el test "
            f"necesita el arreglo para siquiera compilar")

    esperado = next((c for ext, c in FALLO_DE_TEST.items() if ruta.endswith(ext)), 1)
    if code == esperado:
        return CONFIRMADA, "el test falló sobre el código sin arreglar"
    return NO_VERIFICADA, (
        f"el runner terminó con exit {code}, que no es el código con el que declara "
        f"'los tests fallaron' (esperado {esperado}): no se puede afirmar que el test "
        f"haya fallado por comportamiento. Revisa la salida y, si corresponde, "
        f"comprueba la regresión a mano")


def probar(sha, specs, cmd_extra, timeout, verbose):
    if not SHA_RE.match(sha):
        return NO_VERIFICADA, f"'{sha}' no es un hash de commit (no se aceptan HEAD ni branches)", ""
    if git("cat-file", "-e", f"{sha}^{{commit}}").returncode != 0:
        return NO_VERIFICADA, f"el commit {sha} no existe en este repositorio", ""

    padre = git("rev-parse", f"{sha}^")
    if padre.returncode != 0:
        return NO_APLICABLE, "el arreglo es el commit raíz: no hay árbol previo contra el que probar", ""
    padre = padre.stdout.strip()

    rutas = [s.split("::", 1)[0] for s in specs]
    for r in rutas:
        if git("cat-file", "-e", f"{sha}:{r}").returncode != 0:
            return NO_VERIFICADA, f"'{r}' no existe en el commit {sha[:7]}", ""

    tocados = git("show", "--name-only", "--format=", sha).stdout.split()
    traer = sorted(set(rutas) | {t for t in tocados if es_test(t)})

    raiz = Path(git("rev-parse", "--show-toplevel").stdout.strip() or ".")
    tmp = tempfile.mkdtemp(prefix="regresion-")
    wt = str(Path(tmp) / "wt")
    try:
        r = git("worktree", "add", "--detach", "--quiet", wt, padre)
        if r.returncode != 0:
            return NO_VERIFICADA, f"no se pudo crear el worktree: {r.stderr.strip()}", ""

        r = git("checkout", sha, "--", *traer, cwd=wt)
        if r.returncode != 0:
            return NO_VERIFICADA, f"no se pudieron traer los archivos de test: {r.stderr.strip()}", ""

        for d in DEPS:
            origen, destino = raiz / d, Path(wt) / d
            if origen.exists() and not destino.exists():
                destino.parent.mkdir(parents=True, exist_ok=True)
                # Un enlace que no se puede crear (permisos, sistema de archivos sin
                # symlinks) no es fatal: el runner fallará por dependencias y eso se
                # reporta como 'no-verificada', que es la verdad.
                with contextlib.suppress(OSError):
                    os.symlink(origen.resolve(), destino)

        cmd = cmd_extra or comando_para(rutas[0], specs[0])
        if not cmd:
            return NO_VERIFICADA, f"no sé cómo correr '{rutas[0]}': pásalo con --cmd", ""

        try:
            r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True,
                               timeout=timeout, check=False)
        except FileNotFoundError:
            return NO_VERIFICADA, f"el comando '{cmd[0]}' no está instalado", ""
        except subprocess.TimeoutExpired:
            return NO_VERIFICADA, f"el test no terminó en {timeout}s", ""

        salida = (r.stdout or "") + (r.stderr or "")
        if verbose:
            print(salida, file=sys.stderr)
        resultado, razon = interpretar(rutas[0], r.returncode, salida)
        return resultado, razon, salida[-4000:]
    finally:
        git("worktree", "remove", "--force", wt)
        git("worktree", "prune")
        shutil.rmtree(tmp, ignore_errors=True)


SALIDA = {CONFIRMADA: 0, NO_PRUEBA: 1, NO_VERIFICADA: 2, NO_APLICABLE: 2}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--commit", required=True, help="hash del commit del arreglo")
    ap.add_argument("--test", required=True, nargs="+", metavar="RUTA[::NOMBRE]")
    ap.add_argument("--cmd", help="comando para correr el test (si el automático no sirve)")
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("-v", "--verbose", action="store_true", help="mostrar la salida del runner")
    args = ap.parse_args()

    cmd = args.cmd.split() if args.cmd else None
    resultado, razon, salida = probar(args.commit, args.test, cmd, args.timeout, args.verbose)

    if args.json:
        print(json.dumps({"resultado": resultado, "razon": razon,
                          "commit": args.commit, "test": args.test,
                          "salida": salida}, ensure_ascii=False))
    elif resultado == CONFIRMADA:
        print(f"✓ Regresión confirmada: {razon}.")
        print(f"  El test habría atrapado este bug. {args.test[0]}")
    elif resultado == NO_PRUEBA:
        print(f"❌ El test NO demuestra nada: {razon}.")
        print("   Escrito sobre el código ya arreglado, pasa siempre. Tiene que ejercitar")
        print("   el camino que fallaba, con los datos que lo hacían fallar.")
    else:
        print(f"⚠️  No se pudo verificar: {razon}.")
        print("   Esto NO es verde: el test queda declarado, no probado.")

    return SALIDA[resultado]


if __name__ == "__main__":
    sys.exit(main())

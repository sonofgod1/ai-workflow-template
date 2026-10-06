#!/usr/bin/env python3
"""Cruza SPEC.md con los tests y con .last-verify.json.

No lee código de aplicación. Una §V se sostiene si existe un test nombrado
test_v<n> (test_v2_token_expiry vale; test_v20 no cuenta como test_v2) y la
última verificación es de este árbol: mismo HEAD, árbol limpio, resultado ok,
sin --quick.

Uso:
  python3 .workflow/check-spec.py T28
  python3 .workflow/check-spec.py --all
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".next",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "site-packages",
    "venv",
}
TEST_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".go", ".rb", ".java", ".kt", ".rs"}
PLANTILLA = "Andamiaje para construir sistemas digitales con agentes"
IGNORAR_SUCIO = {".workflow/.last-verify.json", ".workflow/.phase.json"}


def split_pipe(line: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(line):
        if line[i] == "\\" and i + 1 < len(line) and line[i + 1] == "|":
            buf.append("|")
            i += 2
            continue
        if line[i] == "|":
            parts.append("".join(buf).strip())
            buf = []
            i += 1
            continue
        buf.append(line[i])
        i += 1
    parts.append("".join(buf).strip())
    return parts


def secciones(texto: str) -> dict[str, str]:
    actual = ""
    bloques: dict[str, list[str]] = {}
    for linea in texto.splitlines():
        if linea.startswith("## §"):
            actual = linea[3:].split()[0]
            bloques[actual] = []
            continue
        if actual:
            bloques[actual].append(linea)
    return {k: "\n".join(v) for k, v in bloques.items()}


def invariantes(bloque: str) -> dict[int, str]:
    found: dict[int, str] = {}
    for linea in bloque.splitlines():
        m = re.match(r"V(\d+):\s*(.*)", linea.strip())
        if m and int(m.group(1)) not in found:
            found[int(m.group(1))] = m.group(2).strip()
    return found


def tareas(bloque: str) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for linea in bloque.splitlines():
        if not linea.startswith("T") or "|" not in linea:
            continue
        celdas = split_pipe(linea)
        if len(celdas) < 4 or not re.fullmatch(r"T\d+", celdas[0]):
            continue
        found[celdas[0]] = {"status": celdas[1], "task": celdas[2], "cites": celdas[3]}
    return found


def deltas(bloque: str) -> list[dict[str, str]]:
    filas = []
    for linea in bloque.splitlines():
        if not linea.startswith("D") or "|" not in linea:
            continue
        celdas = split_pipe(linea)
        if len(celdas) < 5 or not re.fullmatch(r"D\d+", celdas[0]):
            continue
        filas.append(
            {
                "id": celdas[0],
                "op": celdas[1],
                "target": celdas[2],
                "change": celdas[3],
                "cites": celdas[4],
            }
        )
    return filas


def ids_v(cites: str) -> list[int]:
    return [int(n) for n in re.findall(r"V(\d+)", cites)]


def cita_tarea(cites: str, tarea: str) -> bool:
    return tarea in re.split(r"[\s,]+", cites)


def git(root: Path, *args: str) -> str:
    try:
        r = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    if r.returncode != 0:
        return ""
    return r.stdout.strip()


def arbol_limpio(root: Path) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False, "no pude correr git status"
    if r.returncode != 0:
        return False, "no estoy en un repositorio git"
    for linea in r.stdout.splitlines():
        path = linea[3:].strip()
        if path in IGNORAR_SUCIO:
            continue
        return False, "hay cambios sin commitear"
    return True, ""


def razon_evidencia(root: Path) -> str:
    ev_path = root / ".workflow" / ".last-verify.json"
    if not ev_path.is_file():
        return "no hay .workflow/.last-verify.json"
    try:
        data = json.loads(ev_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "no pude leer .last-verify.json"
    head = git(root, "rev-parse", "HEAD")
    if not head:
        return "no estoy en un repositorio git"
    if data.get("git_head") != head:
        return "la evidencia es de otro commit"
    limpio, porque = arbol_limpio(root)
    if not limpio:
        return porque
    if data.get("working_tree_sucio"):
        return "la evidencia se tomó con el árbol sucio"
    if data.get("quick"):
        return "la corrida fue --quick, sin tests"
    if data.get("resultado") != "ok":
        return f"resultado {data.get('resultado')}"
    return ""


def _podar(dirnames: list[str], conservar_workflow: bool) -> None:
    quedarse = []
    for nombre in dirnames:
        if nombre in SKIP_DIRS:
            continue
        if nombre.startswith(".") and not (conservar_workflow and nombre == ".workflow"):
            continue
        quedarse.append(nombre)
    dirnames[:] = quedarse


def es_archivo_de_test(path: Path) -> bool:
    nombre = path.name
    if path.suffix not in TEST_SUFFIXES:
        return False
    if nombre.startswith("test_") or nombre.endswith("_test.py"):
        return True
    return ".test." in nombre or ".spec." in nombre


def buscar_test(root: Path, n: int, incluir_workflow: bool) -> str:
    patron = re.compile(rf"(?<![\w])test_v{n}(?!\d)")
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        if rel.parts[:1] == (".workflow",):
            if not incluir_workflow or (len(rel.parts) >= 2 and rel.parts[1] != "tests"):
                dirnames[:] = []
                continue
            if rel == Path(".workflow"):
                dirnames[:] = ["tests"] if "tests" in dirnames else []
        else:
            _podar(dirnames, incluir_workflow)
        for nombre in filenames:
            if rel.parts[:1] == (".workflow",) and rel == Path(".workflow"):
                continue
            path = Path(dirpath) / nombre
            if not es_archivo_de_test(path):
                continue
            try:
                texto = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if patron.search(texto):
                return str(path.relative_to(root))
    return ""


def puntuar(root: Path, alcance: str) -> tuple[list[str], int]:
    spec_path = root / "SPEC.md"
    if not spec_path.is_file():
        return ["no spec, nothing to check."], 2
    texto = spec_path.read_text(encoding="utf-8")
    secs = secciones(texto)
    vs = invariantes(secs.get("§V", ""))
    ts = tareas(secs.get("§T", ""))
    ds = deltas(secs.get("§D", ""))
    plantilla = PLANTILLA in texto

    if alcance == "--all":
        ids = sorted(vs)
        tareas_alcance = list(ts)
        etiqueta = "--all"
    else:
        tarea = alcance
        if tarea not in ts:
            return [f"no hay {tarea} en SPEC.md"], 2
        ids = ids_v(ts[tarea]["cites"])
        if not ids:
            return [f"{tarea} no cita §V; no hay qué puntuar."], 2
        tareas_alcance = [tarea]
        etiqueta = f"{tarea} · " + ", ".join(f"V{n}" for n in ids)

    evidencia = razon_evidencia(root)
    lineas = ["## check", f"alcance: {etiqueta}", "", "## §V"]
    hold = unver = sin_ev = 0
    for n in ids:
        if n not in vs:
            lineas.append(f"V{n} UNVERIFIABLE: no está en §V")
            unver += 1
            continue
        donde = buscar_test(root, n, plantilla)
        if not donde:
            lineas.append(f"V{n} UNVERIFIABLE: no hay test_v{n}")
            unver += 1
            continue
        if evidencia:
            lineas.append(f"V{n} SIN EVIDENCIA: {donde} existe; {evidencia}")
            sin_ev += 1
            continue
        lineas.append(f"V{n} HOLD: {donde} · verify ok")
        hold += 1

    lineas += ["", "## §T"]
    stale = 0
    for tid in tareas_alcance:
        if ts[tid]["status"] != "x":
            continue
        abiertas = [d for d in ds if cita_tarea(d["cites"], tid)]
        if abiertas:
            ids_d = ", ".join(d["id"] for d in abiertas)
            lineas.append(f"{tid} STALE: status x, {ids_d} sigue en §D")
            stale += 1
    if stale == 0:
        lineas.append("-")

    lineas += ["", "## §D open"]
    abiertas = ds if alcance == "--all" else [d for d in ds if cita_tarea(d["cites"], alcance)]
    if not abiertas:
        lineas.append("-")
    else:
        for d in abiertas:
            lineas.append(f"{d['id']} {d['op']} {d['target']} → {d['cites']}")

    lineas += ["", "## §I", "§I no se puntúa: el script no lee la app.", ""]
    lineas.append(
        f"## summary\n{hold} hold. {unver} unverifiable. {sin_ev} sin evidencia. {stale} stale. "
        f"{len(abiertas)} delta open."
    )
    codigo = 1 if (unver or sin_ev or stale) else 0
    return lineas, codigo


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] in {"-h", "--help"}:
        print("uso: python3 .workflow/check-spec.py T<n> | --all", file=sys.stderr)
        return 2
    arg = argv[1]
    if arg != "--all":
        m = re.fullmatch(r"(?:§T\.)?T?(\d+)", arg)
        if not m:
            print("uso: python3 .workflow/check-spec.py T<n> | --all", file=sys.stderr)
            return 2
        arg = f"T{m.group(1)}"
    root = Path(__file__).resolve().parents[1]
    lineas, codigo = puntuar(root, arg)
    print("\n".join(lineas))
    return codigo


if __name__ == "__main__":
    sys.exit(main(sys.argv))

#!/usr/bin/env python3
"""Separa una copia de la plantilla del repo que la desarrolla.

Correr desde la raíz del proyecto:

    python3 .workflow/bootstrap-proyecto.py
    python3 .workflow/bootstrap-proyecto.py --detect

Imprime una palabra:

    plantilla   este remote (o un clone largo sin remote) es la plantilla. No escribe.
    copia       había spec y verify.conf de la plantilla. Quedó un SPEC stub, se
                borró ese verify.conf y el índice de hallazgos quedó vacío.
                La marca .workflow/es-plantilla se va.
    proyecto    la spec ya es del producto, o no hay marca. No reemplaza SPEC.md.
                Si el índice cita solo commits que no existen aquí, también lo vacía.

--force no alcanza para reescribir el repo cuyo remote se llama ai-workflow-template.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

MARCA = ".workflow/es-plantilla"
REPO_PLANTILLA = "ai-workflow-template"

STUB = """# SPEC

## §G GOAL
[pendiente — /discovery confirma el norte antes de escribirlo]

## §M MODE
spec

## §C CONSTRAINTS
- [pendiente — /discovery clasifica; el stack lo elige /architect]

## §I INTERFACES
- [pendiente — /spec, con el stack ya elegido o dejado pendiente a propósito]

## §V INVARIANTS
- [pendiente — /spec]

## §T TASKS
id|status|task|cites
-|-|-|-

## §B BUGS
id|date|cause|fix
-|-|-|-

## §D DELTA
id|op|target|change|cites
-|-|-|-|-
"""


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def nombre_repo(url: str) -> str:
    limpio = url.strip().rstrip("/")
    if limpio.endswith(".git"):
        limpio = limpio[:-4]
    cola = limpio.split(":")[-1]
    return cola.split("/")[-1]


def remotos(root: Path) -> list[str]:
    salida = _git(root, "remote", "-v").stdout
    urls = []
    for linea in salida.splitlines():
        partes = linea.split()
        if len(partes) >= 2:
            urls.append(partes[1])
    return urls


def commits(root: Path) -> int:
    resultado = _git(root, "rev-list", "--count", "HEAD")
    if resultado.returncode != 0:
        return 0
    try:
        return int(resultado.stdout.strip() or "0")
    except ValueError:
        return 0


def es_repo_de_la_plantilla(root: Path) -> bool:
    urls = remotos(root)
    if any(nombre_repo(url) == REPO_PLANTILLA for url in urls):
        return True
    # Clone de desarrollo al que todavía no le cargaron el remote.
    # Un proyecto nuevo sale del botón template con un solo commit, o sin historia.
    return not urls and commits(root) > 1


def leer_goal(marca: Path) -> str:
    for linea in marca.read_text(encoding="utf-8").splitlines():
        if linea.startswith("goal="):
            return linea.split("=", 1)[1].strip()
    return ""


def cuerpo_g(texto: str) -> str:
    marca = "## §G GOAL"
    inicio = texto.find(marca)
    if inicio < 0:
        return ""
    resto = texto[inicio + len(marca) :]
    fin = resto.find("\n## ")
    cuerpo = resto if fin < 0 else resto[:fin]
    return cuerpo.strip()


def spec_es_de_la_plantilla(texto: str, goal: str) -> bool:
    if not goal:
        return False
    cuerpo = cuerpo_g(texto)
    return bool(cuerpo) and "[pendiente" not in cuerpo and cuerpo.startswith(goal)


def verify_es_de_la_plantilla(texto: str) -> bool:
    return "Contrato de verificación de la plantilla." in texto and "tests-andamiaje" in texto


def _render_decisiones(data: dict) -> str:
    ruta = Path(__file__).resolve().parent / "findings.py"
    spec = importlib.util.spec_from_file_location("findings_bootstrap", ruta)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"no se pudo cargar {ruta}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.render_decisiones(data)


def _commit_existe(root: Path, sha: str) -> bool:
    return _git(root, "cat-file", "-e", f"{sha}^{{commit}}").returncode == 0


def vaciar_indice(root: Path, *, forzar: bool) -> None:
    """Saca del proyecto el índice de hallazgos de la plantilla.

    En una copia el archivo entero es de la plantilla, aunque el clone haya
    traído su historia y los hashes existan. En un proyecto ya arrancado solo
    se quitan las filas cuyo commit no está en este repo: un hallazgo propio,
    con hash de aquí, se queda.
    """
    indice = root / "docs" / "findings.json"
    if not indice.is_file():
        return
    data = json.loads(indice.read_text(encoding="utf-8"))
    hallazgos = list(data.get("hallazgos") or [])
    if forzar:
        propios = []
    else:
        propios = [h for h in hallazgos if not h.get("commit") or _commit_existe(root, h["commit"])]
    if propios == hallazgos:
        return
    nuevo = {"version": data.get("version", 1), "hallazgos": propios}
    indice.write_text(
        json.dumps(nuevo, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    decisiones = root / "docs" / "reviews" / "decisiones.md"
    decisiones.parent.mkdir(parents=True, exist_ok=True)
    decisiones.write_text(_render_decisiones(nuevo), encoding="utf-8")


def iniciar(root: Path) -> None:
    (root / "SPEC.md").write_text(STUB, encoding="utf-8")
    verify = root / ".workflow" / "verify.conf"
    if verify.is_file() and verify_es_de_la_plantilla(verify.read_text(encoding="utf-8")):
        verify.unlink()
    vaciar_indice(root, forzar=True)
    marca = root / MARCA
    if marca.exists():
        marca.unlink()


def estado(root: Path) -> str:
    if es_repo_de_la_plantilla(root):
        return "plantilla"
    marca = root / MARCA
    if not marca.is_file():
        return "proyecto"
    spec = root / "SPEC.md"
    texto = spec.read_text(encoding="utf-8") if spec.is_file() else ""
    if spec_es_de_la_plantilla(texto, leer_goal(marca)):
        return "copia"
    return "proyecto"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    detectar = "--detect" in args
    forzar = "--force" in args
    root = Path.cwd()

    if es_repo_de_la_plantilla(root):
        if forzar:
            print(
                "este remote es la plantilla. No se reescribe su SPEC.md.",
                file=sys.stderr,
            )
            return 2
        print("plantilla")
        return 0

    actual = estado(root)
    if actual == "proyecto":
        marca = root / MARCA
        # Marca colgada de un overlay: la spec ya no es la de la plantilla.
        if marca.exists():
            marca.unlink()
        if not detectar:
            vaciar_indice(root, forzar=False)
        print("proyecto")
        return 0

    if detectar:
        print("copia")
        return 0

    iniciar(root)
    print("copia")
    return 0


if __name__ == "__main__":
    sys.exit(main())

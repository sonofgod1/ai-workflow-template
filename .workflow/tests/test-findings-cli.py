#!/usr/bin/env python3
"""Regresión de la ergonomía de findings.py (hallazgo S1 y alrededores).

Ninguna de estas asperezas rompía nada, y por eso sobrevivieron. Lo que hacían era
empujar al camino de menor resistencia equivocado: si anotar cuesta una ceremonia
rara, la nota termina solo en el reporte y el índice —que es lo que CI valida y lo
que alimenta decisiones.md— se queda sin el porqué. Si reclasificar exige editar el
JSON a mano, se edita a mano y validate pelea con el resultado.

    python3 .workflow/tests/test-findings-cli.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FINDINGS = RAIZ / "findings.py"


def fnd(repo, *args, esperar_exito=True):
    r = subprocess.run([sys.executable, str(FINDINGS), *args],
                       cwd=repo, capture_output=True, text=True, check=False)
    if esperar_exito:
        assert r.returncode == 0, f"findings.py {' '.join(args)} falló: {r.stdout}{r.stderr}"
    return r


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


def montar(repo):
    """Repo mínimo con un reporte de origen que exista, y un hallazgo abierto."""
    git(repo, "init", "-q", ".")
    git(repo, "config", "user.email", "t@t.t")
    git(repo, "config", "user.name", "t")
    d = Path(repo) / "docs" / "reviews"
    d.mkdir(parents=True)
    (d / "r.md").write_text("# review\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "docs: review")
    fnd(repo, "add", "--id", "I1", "--severidad", "important",
        "--titulo", "algo pasa", "--origen", "docs/reviews/r.md")


def indice(repo):
    return json.loads((Path(repo) / "docs" / "findings.json").read_text(encoding="utf-8"))


def hallazgo(repo, hid):
    for h in indice(repo)["hallazgos"]:
        if h["id"] == hid:
            return h
    return None


# ── Casos ────────────────────────────────────────────────────────────────────

def caso_anotar_sin_tocar_el_estado():
    """S1: anotar es lo más frecuente; no puede exigir declarar un cambio de estado."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        fnd(d, "nota", "I1", "esto se descartó porque el caso no se da en producción")
        h = hallazgo(d, "I1")
        assert "se descartó" in (h["nota"] or ""), h
        assert h["estado"] == "abierto", "anotar no puede cambiar el estado: " + str(h)


def caso_estado_sin_nuevo_ya_no_falla():
    """Antes --nuevo era obligatorio, y obligaba al absurdo 'abierto -> abierto'."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        r = fnd(d, "estado", "I1", "--nota", "una nota suelta", esperar_exito=False)
        assert r.returncode == 0, f"estado --nota sin --nuevo falló: {r.stdout}{r.stderr}"
        assert hallazgo(d, "I1")["estado"] == "abierto"


def caso_estado_sin_nada_avisa():
    """Aflojar --nuevo no puede volver silencioso un comando que no hace nada."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        r = fnd(d, "estado", "I1", esperar_exito=False)
        assert r.returncode != 0, "un 'estado' sin cambios tiene que fallar"
        assert "Nada que cambiar" in (r.stdout + r.stderr)


def caso_nota_agregar_no_pisa():
    """Una nota nueva no debería borrar el porqué que ya estaba, si no se quiere."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        fnd(d, "nota", "I1", "primera razón.")
        fnd(d, "nota", "I1", "segunda razón.", "--agregar")
        nota = hallazgo(d, "I1")["nota"]
        assert "primera razón." in nota and "segunda razón." in nota, nota


def caso_add_acepta_nota():
    """El porqué se sabe al registrar; obligar a un segundo comando lo pierde."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        fnd(d, "add", "--id", "I2", "--severidad", "important", "--titulo", "otra",
            "--origen", "docs/reviews/r.md", "--nota", "sale de la prueba manual")
        assert "prueba manual" in (hallazgo(d, "I2")["nota"] or "")


def caso_archivos_con_comas():
    """'a.py,b.py' entraba como UNA ruta con una coma adentro, sin avisar."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        fnd(d, "add", "--id", "I2", "--severidad", "important", "--titulo", "otra",
            "--origen", "docs/reviews/r.md", "--archivos", "a.py,b.py", "c.py")
        archivos = hallazgo(d, "I2")["archivos"]
        assert archivos == ["a.py", "b.py", "c.py"], archivos


def caso_reclasificar_cambia_id_y_severidad():
    """Pasó con I3 en musicos: la única salida era editar el JSON a mano."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        fnd(d, "severidad", "I1", "--nueva", "suggestion",
            "--razon", "la prueba manual mostró que no bloquea nada")
        assert hallazgo(d, "I1") is None, "el id viejo tiene que dejar de existir"
        h = hallazgo(d, "S1")
        assert h is not None, indice(d)
        assert h["severidad"] == "suggestion", h
        assert h["renombrado_de"] == "I1", "se pierde el rastro del id viejo"
        assert "la prueba manual" in (h["nota"] or ""), h


def caso_reclasificar_deja_el_indice_valido():
    """validate exige que el prefijo del id coincida con la severidad."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        fnd(d, "severidad", "I1", "--nueva", "suggestion")
        r = fnd(d, "validate", esperar_exito=False)
        assert r.returncode == 0, f"el índice quedó inconsistente: {r.stdout}{r.stderr}"


def caso_no_reclasifica_uno_resuelto():
    """Su id ya está escrito en un mensaje de commit: renombrarlo cuelga el historial."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        (Path(d) / "x.txt").write_text("x\n", encoding="utf-8")
        git(d, "add", "-A")
        git(d, "commit", "-q", "-m", "fix(I1): algo")
        sha = git(d, "rev-parse", "HEAD").stdout.strip()[:9]
        fnd(d, "cerrar", "I1", "--commit", sha, "--sin-test", "--razon", "cambio de copy")
        r = fnd(d, "severidad", "I1", "--nueva", "suggestion", esperar_exito=False)
        assert r.returncode != 0, "reclasificó un hallazgo ya cerrado"
        assert "historial" in (r.stdout + r.stderr)


CASOS = [
    caso_anotar_sin_tocar_el_estado,
    caso_estado_sin_nuevo_ya_no_falla,
    caso_estado_sin_nada_avisa,
    caso_nota_agregar_no_pisa,
    caso_add_acepta_nota,
    caso_archivos_con_comas,
    caso_reclasificar_cambia_id_y_severidad,
    caso_reclasificar_deja_el_indice_valido,
    caso_no_reclasifica_uno_resuelto,
]


def main():
    fallos = 0
    for caso in CASOS:
        try:
            caso()
            print(f"  ✓ {caso.__name__} — {(caso.__doc__ or '').strip().splitlines()[0]}")
        except AssertionError as exc:
            fallos += 1
            print(f"  ✗ {caso.__name__}: {exc}")
    print()
    if fallos:
        print(f"❌ {fallos} de {len(CASOS)} casos fallaron.")
        return 1
    print(f"✓ {len(CASOS)} casos en verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

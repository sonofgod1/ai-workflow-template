#!/usr/bin/env python3
"""Regresión del generador de decisiones.md (findings.py).

El riesgo de un archivo generado que se versiona es que deje de ser determinista:
si el texto cambia sin que el índice cambie, `--check` falla en CI un día
cualquiera y la gente aprende a ignorarlo. Por eso el primer caso es que dos
renders del mismo índice sean idénticos byte a byte, y el segundo que no aparezca
la fecha de hoy en el archivo.

El otro riesgo es el drift que este cambio existe para eliminar: que una mutación
del índice no llegue al markdown.

    python3 .workflow/tests/test-decisiones.py
"""

import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
FINDINGS = RAIZ / "findings.py"
DECISIONES = Path("docs/reviews/decisiones.md")


def fnd(repo, *args, esperar_exito=True):
    r = subprocess.run([sys.executable, str(FINDINGS), *args],
                       cwd=repo, capture_output=True, text=True, check=False)
    if esperar_exito:
        assert r.returncode == 0, f"findings.py {' '.join(args)} falló: {r.stdout}{r.stderr}"
    return r


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)


def montar(repo):
    """Repo con un hallazgo abierto, uno resuelto con test y uno descartado."""
    git(repo, "init", "-q", ".")
    git(repo, "config", "user.email", "t@t.t")
    git(repo, "config", "user.name", "t")
    (Path(repo) / "docs" / "reviews").mkdir(parents=True)
    (Path(repo) / "docs" / "reviews" / "r.md").write_text("# review\n", encoding="utf-8")
    (Path(repo) / "tests").mkdir()
    (Path(repo) / "tests" / "test-x.sh").write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "fix: algo")
    sha = git(repo, "rev-parse", "HEAD").stdout.strip()

    fnd(repo, "add", "--id", "B1", "--severidad", "blocker",
        "--titulo", "PUT no es atómico", "--origen", "docs/reviews/r.md",
        "--archivos", "api.py:88")
    fnd(repo, "add", "--id", "B2", "--severidad", "blocker",
        "--titulo", "otro", "--origen", "docs/reviews/r.md")
    fnd(repo, "add", "--id", "I1", "--severidad", "important",
        "--titulo", "no urgente", "--origen", "docs/reviews/r.md")
    fnd(repo, "cerrar", "B2", "--commit", sha, "--test", "tests/test-x.sh")
    fnd(repo, "estado", "I1", "--nuevo", "descartado", "--nota", "el caso no puede ocurrir")
    return sha


def leer(repo):
    return (Path(repo) / DECISIONES).read_text(encoding="utf-8")


# ── Casos ────────────────────────────────────────────────────────────────────

def caso_determinista():
    """Dos renders del mismo índice son idénticos: sin esto, --check es inservible."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        primero = leer(d)
        fnd(d, "decisiones")
        assert leer(d) == primero, "el render cambió sin que cambiara el índice"


def caso_sin_fecha_de_hoy():
    """Una fecha de generación haría fallar --check al día siguiente."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        texto = leer(d)
        hoy = date.today().isoformat()
        # La fecha de resolución de un hallazgo sí es dato del índice; lo que no puede
        # haber es una fecha de generación. Se comprueba en la cabecera.
        cabecera = texto.split("## ")[0]
        assert hoy not in cabecera, f"la cabecera lleva la fecha de hoy:\n{cabecera}"


def caso_se_escribe_solo():
    """Cada mutación del índice llega al markdown sin un paso manual."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        assert (Path(d) / DECISIONES).exists(), "no se generó en la primera mutación"
        assert "PUT no es atómico" in leer(d)
        fnd(d, "add", "--id", "S1", "--severidad", "suggestion",
            "--titulo", "renombrar variable", "--origen", "docs/reviews/r.md")
        assert "renombrar variable" in leer(d), "un add posterior no llegó al markdown"


def caso_secciones_por_estado():
    """Abierto, resuelto y descartado caen en secciones distintas."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        t = leer(d)
        assert "Arreglar ahora" in t and "B1" in t
        assert "✅ Resueltos" in t and "B2" in t
        assert "⚪ Descartados" in t and "el caso no puede ocurrir" in t
        # B2 está cerrado: no puede seguir apareciendo como pendiente.
        pendientes = t.split("## ✅ Resueltos")[0]
        assert "B2" not in pendientes, "un hallazgo cerrado sigue listado como pendiente"


def caso_estado_del_test_visible():
    """El markdown muestra si el cierre tuvo test probado, declarado o exento."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        assert "declarado" in leer(d), "no se ve el estado del test"


def caso_check_detecta_edicion_a_mano():
    """Editarlo a mano tiene que fallar en CI, no perderse en silencio."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        assert fnd(d, "decisiones", "--check").returncode == 0
        p = Path(d) / DECISIONES
        p.write_text(leer(d) + "\n(nota escrita a mano)\n", encoding="utf-8")
        r = fnd(d, "decisiones", "--check", esperar_exito=False)
        assert r.returncode == 1, "una edición a mano pasó el --check"
        assert "desactualizado" in r.stdout, r.stdout


def caso_check_detecta_ausencia():
    """Si el archivo no existe, --check falla en vez de asumir que está bien."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        (Path(d) / DECISIONES).unlink()
        r = fnd(d, "decisiones", "--check", esperar_exito=False)
        assert r.returncode == 1 and "no existe" in r.stdout, r.stdout


def caso_orden_numerico():
    """B10 va después de B2: ordenar ids como texto haría inestable el archivo."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        for n in (10, 3):
            fnd(d, "add", "--id", f"B{n}", "--severidad", "blocker",
                "--titulo", f"hallazgo {n}", "--origen", "docs/reviews/r.md")
        t = leer(d)
        pos = [t.index(f"| B{n} ") for n in (1, 3, 10)]
        assert pos == sorted(pos), f"orden incorrecto: {pos}"


def caso_pipe_en_el_titulo():
    """Un pipe en el título no puede romper la tabla markdown."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        fnd(d, "add", "--id", "S2", "--severidad", "suggestion",
            "--titulo", "usar a || b en vez de or", "--origen", "docs/reviews/r.md")
        fila = next(linea for linea in leer(d).splitlines() if linea.startswith("| S2 "))
        assert fila.count("|") - fila.count("\\|") == 7, f"columnas rotas: {fila}"


def caso_indice_vacio():
    """Un índice sin hallazgos genera un archivo válido, no un crash."""
    with tempfile.TemporaryDirectory() as d:
        git(d, "init", "-q", ".")
        (Path(d) / "docs").mkdir()
        (Path(d) / "docs" / "findings.json").write_text(
            json.dumps({"version": 1, "hallazgos": []}), encoding="utf-8")
        fnd(d, "decisiones")
        assert "Sin hallazgos registrados" in leer(d)


CASOS = [
    caso_determinista,
    caso_sin_fecha_de_hoy,
    caso_se_escribe_solo,
    caso_secciones_por_estado,
    caso_estado_del_test_visible,
    caso_check_detecta_edicion_a_mano,
    caso_check_detecta_ausencia,
    caso_orden_numerico,
    caso_pipe_en_el_titulo,
    caso_indice_vacio,
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

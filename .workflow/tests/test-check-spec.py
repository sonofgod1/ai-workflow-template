#!/usr/bin/env python3
"""V5: /check es check-spec.py. No lee la app ni el venv.

python3 .workflow/tests/test-check-spec.py
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / ".workflow" / "check-spec.py"


def cargar():
    spec = importlib.util.spec_from_file_location("check_spec", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MOD = cargar()

SPEC = """# SPEC

## §G GOAL
demo

## §M MODE
spec

## §C CONSTRAINTS
- x

## §I INTERFACES
- api: GET /x → 200

## §V INVARIANTS
V1: algo se sostiene
V2: otra cosa
V10: no es la uno

## §T TASKS
id|status|task|cites
T1|x|hace uno|V1
T2|.|hace dos|V2,V10
T3|x|sin fold|V2
T4|.|sin invariante|-

## §B BUGS
id|date|cause|fix

## §D DELTA
id|op|target|change|cites
D1|ADDED|§I|api: POST /y → 200|T3
"""


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)


def montar(base, spec=SPEC):
    proy = Path(base) / "p"
    proy.mkdir()
    sh(proy, "git", "init", "-q", "-b", "main")
    sh(proy, "git", "config", "user.email", "t@t.t")
    sh(proy, "git", "config", "user.name", "t")
    (proy / "SPEC.md").write_text(spec, encoding="utf-8")
    (proy / ".gitignore").write_text(".workflow/.last-verify.json\n", encoding="utf-8")
    (proy / "tests").mkdir()
    (proy / "tests" / "test_v1_existe.py").write_text(
        "def test_v1_existe():\n    assert True\n",
        encoding="utf-8",
    )
    (proy / "tests" / "test_v10_diez.py").write_text(
        "def test_v10_diez():\n    assert True\n",
        encoding="utf-8",
    )
    sh(proy, "git", "add", "-A")
    sh(proy, "git", "commit", "-qm", "test: seed")
    return proy


def evidencia(proy, **cambios):
    head = sh(proy, "git", "rev-parse", "HEAD").stdout.strip()
    data = {
        "git_head": head,
        "working_tree_sucio": False,
        "quick": False,
        "resultado": "ok",
    }
    data.update(cambios)
    path = proy / ".workflow" / ".last-verify.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_v5_hold_con_verify_de_este_arbol():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        evidencia(proy)
        lineas, codigo = MOD.puntuar(proy, "T1")
        texto = "\n".join(lineas)
        assert codigo == 0, texto
        assert "V1 HOLD: tests/test_v1_existe.py · verify ok" in texto
        assert "STALE" not in texto


def test_v5_test_v10_no_cubre_v1():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        evidencia(proy)
        (proy / "tests" / "test_v1_existe.py").unlink()
        sh(proy, "git", "add", "-A")
        sh(proy, "git", "commit", "-qm", "test: sin v1")
        evidencia(proy)
        lineas, codigo = MOD.puntuar(proy, "T1")
        texto = "\n".join(lineas)
        assert codigo == 1, texto
        assert "V1 UNVERIFIABLE: no hay test_v1" in texto


def test_v5_ignora_venv_y_workflow_de_consumidor():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        evidencia(proy)
        (proy / "tests" / "test_v1_existe.py").unlink()
        falso = proy / ".venv" / "lib"
        falso.mkdir(parents=True)
        (falso / "test_v1_falso.py").write_text("def test_v1_falso():\n    pass\n", encoding="utf-8")
        andamio = proy / ".workflow" / "tests"
        andamio.mkdir(parents=True)
        (andamio / "test_v1_plantilla.py").write_text(
            "def test_v1_plantilla():\n    pass\n", encoding="utf-8"
        )
        sh(proy, "git", "add", "-A")
        sh(proy, "git", "commit", "-qm", "test: solo falsos")
        evidencia(proy)
        lineas, codigo = MOD.puntuar(proy, "T1")
        texto = "\n".join(lineas)
        assert "V1 UNVERIFIABLE" in texto, texto
        assert codigo == 1


def test_v5_plantilla_acepta_test_en_workflow():
    spec = SPEC.replace("## §G GOAL\ndemo", "## §G GOAL\n" + MOD.PLANTILLA)
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d, spec)
        (proy / "tests" / "test_v1_existe.py").unlink()
        andamio = proy / ".workflow" / "tests"
        andamio.mkdir(parents=True)
        (andamio / "test_v1_plantilla.py").write_text(
            "def test_v1_plantilla():\n    pass\n", encoding="utf-8"
        )
        sh(proy, "git", "add", "-A")
        sh(proy, "git", "commit", "-qm", "test: test del andamiaje")
        evidencia(proy)
        lineas, codigo = MOD.puntuar(proy, "T1")
        texto = "\n".join(lineas)
        assert codigo == 0, texto
        assert "V1 HOLD: .workflow/tests/test_v1_plantilla.py" in texto


def test_v5_sin_evidencia_si_el_commit_no_coincide():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        evidencia(proy, git_head="a" * 40)
        lineas, codigo = MOD.puntuar(proy, "T1")
        texto = "\n".join(lineas)
        assert codigo == 1, texto
        assert "SIN EVIDENCIA" in texto
        assert "otro commit" in texto


def test_v5_stale_si_delta_cita_tarea_cerrada():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        evidencia(proy)
        lineas, codigo = MOD.puntuar(proy, "T3")
        texto = "\n".join(lineas)
        assert codigo == 1, texto
        assert "V2 UNVERIFIABLE" in texto
        assert "T3 STALE: status x, D1 sigue en §D" in texto
        assert "D1 ADDED" in texto


def test_v5_tarea_inexistente_y_sin_v():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        lineas, codigo = MOD.puntuar(proy, "T99")
        assert codigo == 2
        assert "no hay T99" in lineas[0]
        lineas, codigo = MOD.puntuar(proy, "T4")
        assert codigo == 2
        assert "no cita §V" in lineas[0]


def test_v5_all_no_abre_codigo_de_app():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        evidencia(proy)
        (proy / "app.py").write_text(
            "def test_v2_esto_no_es_un_test_file_wait():\n    pass\n", encoding="utf-8"
        )
        sh(proy, "git", "add", "-A")
        sh(proy, "git", "commit", "-qm", "test: app")
        evidencia(proy)
        lineas, codigo = MOD.puntuar(proy, "--all")
        texto = "\n".join(lineas)
        assert "V1 HOLD" in texto
        assert "V10 HOLD" in texto
        assert "V2 UNVERIFIABLE" in texto, texto
        assert "§I no se puntúa" in texto
        assert codigo == 1


CASOS = [
    test_v5_hold_con_verify_de_este_arbol,
    test_v5_test_v10_no_cubre_v1,
    test_v5_ignora_venv_y_workflow_de_consumidor,
    test_v5_plantilla_acepta_test_en_workflow,
    test_v5_sin_evidencia_si_el_commit_no_coincide,
    test_v5_stale_si_delta_cita_tarea_cerrada,
    test_v5_tarea_inexistente_y_sin_v,
    test_v5_all_no_abre_codigo_de_app,
]


def main():
    fallos = 0
    for caso in CASOS:
        try:
            caso()
            print(f"  ✓ {caso.__name__}")
        except AssertionError as exc:
            fallos += 1
            print(f"  ✗ {caso.__name__}: {exc}")
        except subprocess.CalledProcessError as exc:
            fallos += 1
            print(f"  ✗ {caso.__name__}: {exc} {exc.stderr}")
    if fallos:
        print(f"❌ {fallos} de {len(CASOS)} casos fallaron.")
        return 1
    print(f"✓ {len(CASOS)} casos en verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

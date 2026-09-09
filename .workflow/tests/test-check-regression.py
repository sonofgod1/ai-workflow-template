#!/usr/bin/env python3
"""Regresión de check-regression.py.

Lo que este script pone en riesgo es el falso verde: decir "regresión confirmada"
cuando el test en realidad pasa sin el arreglo. Ese es el caso que más importa y va
primero. El segundo riesgo es lo contrario — declarar 'no-verificada' por un fallo
de andamiaje (worktree, dependencias) y que el usuario deje de usar el chequeo.

Cada caso monta un repositorio git de verdad en un temporal: un commit con el bug,
otro con el arreglo. Sin repo real no se puede probar nada de esto, porque el
mecanismo ES el worktree.

    python3 .workflow/tests/test-check-regression.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "check-regression.py"

# El test se corre con bash a propósito: pytest no está garantizado en la máquina
# de nadie, y el mecanismo bajo prueba es independiente del runner.
CMD = "bash tests/test-suma.sh"

TEST_BUENO = """#!/usr/bin/env bash
# Ejercita el caso que fallaba: sumar con un negativo.
R=$(bash src/suma.sh 5 -2)
[ "$R" = "3" ] || { echo "esperaba 3, obtuve $R"; exit 1; }
echo ok
"""

TEST_INUTIL = """#!/usr/bin/env bash
# Solo toca el camino que ya funcionaba: pasa con o sin el arreglo.
R=$(bash src/suma.sh 2 2)
[ "$R" = "4" ] || { echo "esperaba 4, obtuve $R"; exit 1; }
echo ok
"""

SUMA_CON_BUG = """#!/usr/bin/env bash
# Bug: ignora el signo del segundo operando.
echo $(( $1 + ${2#-} ))
"""

SUMA_ARREGLADA = """#!/usr/bin/env bash
echo $(( $1 + $2 ))
"""


def git(repo, *args):
    r = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    assert r.returncode == 0, f"git {' '.join(args)} falló: {r.stderr}"
    return r.stdout.strip()


def escribir(repo, ruta, contenido):
    p = Path(repo) / ruta
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contenido, encoding="utf-8")


def montar(repo, test_contenido, test_en_commit_del_arreglo=True):
    """Deja el repo con dos commits: bug y arreglo. Devuelve el sha del arreglo."""
    git(repo, "init", "-q", ".")
    git(repo, "config", "user.email", "t@t.t")
    git(repo, "config", "user.name", "t")
    escribir(repo, "src/suma.sh", SUMA_CON_BUG)
    if not test_en_commit_del_arreglo:
        escribir(repo, "tests/test-suma.sh", test_contenido)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "feat: suma")

    escribir(repo, "src/suma.sh", SUMA_ARREGLADA)
    if test_en_commit_del_arreglo:
        escribir(repo, "tests/test-suma.sh", test_contenido)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "fix: respetar el signo")
    return git(repo, "rev-parse", "HEAD")


def correr(repo, sha, test="tests/test-suma.sh", cmd=CMD):
    argv = [sys.executable, str(SCRIPT), "--commit", sha, "--test", test, "--json"]
    if cmd:
        argv += ["--cmd", cmd]
    r = subprocess.run(argv, cwd=repo, capture_output=True, text=True, check=False)
    try:
        return json.loads(r.stdout.strip().splitlines()[-1]), r.returncode
    except (ValueError, IndexError):
        raise AssertionError(f"sin JSON. out={r.stdout!r} err={r.stderr!r}")


# ── Casos ────────────────────────────────────────────────────────────────────

def caso_test_bueno():
    """El test ejercita el camino que fallaba: tiene que confirmar la regresión."""
    with tempfile.TemporaryDirectory() as d:
        sha = montar(d, TEST_BUENO)
        out, code = correr(d, sha)
        assert out["resultado"] == "confirmada", out
        assert code == 0, code


def caso_test_inutil():
    """El test pasa sin el arreglo: el falso verde que este script existe para atrapar."""
    with tempfile.TemporaryDirectory() as d:
        sha = montar(d, TEST_INUTIL)
        out, code = correr(d, sha)
        assert out["resultado"] == "no-prueba-nada", out
        assert code == 1, code


def caso_test_preexistente_que_ya_pasaba():
    """Test viejo que no cubre el hallazgo: no basta con que exista."""
    with tempfile.TemporaryDirectory() as d:
        sha = montar(d, TEST_INUTIL, test_en_commit_del_arreglo=False)
        out, code = correr(d, sha)
        assert out["resultado"] == "no-prueba-nada", out


def caso_test_inexistente():
    """Nombrar un test que no está en el commit no puede pasar por verde."""
    with tempfile.TemporaryDirectory() as d:
        sha = montar(d, TEST_BUENO)
        out, code = correr(d, sha, test="tests/no-existe.sh")
        assert out["resultado"] == "no-verificada", out
        assert "no existe en el commit" in out["razon"], out
        assert code == 2, code


def caso_commit_simbolico():
    """HEAD existe siempre; aceptarlo dejaría probar contra algo no commiteado."""
    with tempfile.TemporaryDirectory() as d:
        montar(d, TEST_BUENO)
        out, code = correr(d, "HEAD")
        assert out["resultado"] == "no-verificada", out
        assert code == 2, code


def caso_commit_raiz():
    """Sin árbol previo no hay nada contra lo que probar: se dice, no se inventa."""
    with tempfile.TemporaryDirectory() as d:
        git(d, "init", "-q", ".")
        git(d, "config", "user.email", "t@t.t")
        git(d, "config", "user.name", "t")
        escribir(d, "src/suma.sh", SUMA_ARREGLADA)
        escribir(d, "tests/test-suma.sh", TEST_BUENO)
        git(d, "add", "-A")
        git(d, "commit", "-q", "-m", "feat: inicial")
        sha = git(d, "rev-parse", "HEAD")
        out, code = correr(d, sha)
        assert out["resultado"] == "no-aplicable", out
        assert code == 2, code


def caso_runner_ausente():
    """Un runner que no existe es 'no-verificada', nunca 'confirmada'."""
    with tempfile.TemporaryDirectory() as d:
        sha = montar(d, TEST_BUENO)
        out, code = correr(d, sha, cmd="runner-que-no-existe-xyz")
        assert out["resultado"] == "no-verificada", out
        assert code == 2, code


def caso_worktree_limpio():
    """El worktree temporal no puede quedar registrado tras la corrida."""
    with tempfile.TemporaryDirectory() as d:
        sha = montar(d, TEST_BUENO)
        correr(d, sha)
        lista = subprocess.run(["git", "worktree", "list"], cwd=d,
                               capture_output=True, text=True, check=False).stdout
        assert "regresion-" not in lista, lista


CASOS = [
    caso_test_bueno,
    caso_test_inutil,
    caso_test_preexistente_que_ya_pasaba,
    caso_test_inexistente,
    caso_commit_simbolico,
    caso_commit_raiz,
    caso_runner_ausente,
    caso_worktree_limpio,
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

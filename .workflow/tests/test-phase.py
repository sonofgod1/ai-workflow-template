#!/usr/bin/env python3
"""Regresión del aislamiento de la fase por worktree.

El riesgo es el candado global disfrazado de estado local: dos agentes en dos
worktrees del mismo repositorio escribiendo el mismo .phase.json. El segundo pisa
la fase del primero, los hooks del primero empiezan a aplicar la política del
segundo, y nada avisa. Ese caso va primero.

El riesgo opuesto, y peor, es que al arreglarlo la raíz se resuelva a OTRO
repositorio: un hook de protección leyendo el protected.txt del repo de al lado
deja pasar todo. También está cubierto.

    python3 .workflow/tests/test-phase.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PROYECTO = RAIZ.parent


def sh(cmd, cwd=None, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True,
                          check=False, env=e)


def montar(base):
    """Repo con phase.sh y lib-root.sh, más un worktree."""
    repo = Path(base) / "repo"
    (repo / ".workflow").mkdir(parents=True)
    (repo / ".claude" / "hooks").mkdir(parents=True)
    (repo / ".workflow" / "phase.sh").write_bytes((RAIZ / "phase.sh").read_bytes())
    (repo / ".claude" / "hooks" / "lib-root.sh").write_bytes(
        (PROYECTO / ".claude" / "hooks" / "lib-root.sh").read_bytes())
    sh("git init -q -b main . && git config user.email t@t.t && git config user.name t", cwd=repo)
    sh("git add -A && git commit -q -m base", cwd=repo)
    wt = Path(base) / "wt"
    sh(f"git worktree add -q --detach '{wt}' HEAD", cwd=repo)
    return repo, wt


def fase(d, env=None):
    r = sh("bash .workflow/phase.sh show", cwd=d, env=env)
    return r.stdout.strip()


# ── Aislamiento ──────────────────────────────────────────────────────────────

def caso_worktrees_independientes():
    """Cada worktree tiene su propia fase, aunque CLAUDE_PROJECT_DIR sea el principal."""
    with tempfile.TemporaryDirectory() as d:
        repo, wt = montar(d)
        env = {"CLAUDE_PROJECT_DIR": str(repo)}
        sh("bash .workflow/phase.sh set review", cwd=repo, env=env)
        sh("bash .workflow/phase.sh set build", cwd=wt, env=env)
        assert "review" in fase(repo, env), fase(repo, env)
        assert "build" in fase(wt, env), fase(wt, env)


def caso_el_worktree_no_pisa_al_principal():
    """El bug original: un set desde el worktree borraba la fase del principal."""
    with tempfile.TemporaryDirectory() as d:
        repo, wt = montar(d)
        env = {"CLAUDE_PROJECT_DIR": str(repo)}
        sh("bash .workflow/phase.sh set review", cwd=repo, env=env)
        antes = fase(repo, env)
        sh("bash .workflow/phase.sh set implement", cwd=wt, env=env)
        assert fase(repo, env) == antes, f"la fase del principal cambió:\n{antes}\n→\n{fase(repo, env)}"


def caso_clear_no_cruza():
    """Limpiar en un worktree no libera la fase del otro."""
    with tempfile.TemporaryDirectory() as d:
        repo, wt = montar(d)
        env = {"CLAUDE_PROJECT_DIR": str(repo)}
        sh("bash .workflow/phase.sh set review", cwd=repo, env=env)
        sh("bash .workflow/phase.sh set build", cwd=wt, env=env)
        sh("bash .workflow/phase.sh clear", cwd=wt, env=env)
        assert "review" in fase(repo, env), fase(repo, env)
        assert "Sin fase" in fase(wt, env), fase(wt, env)


def caso_archivo_en_cada_worktree():
    """El estado vive en el worktree, no en un sitio compartido."""
    with tempfile.TemporaryDirectory() as d:
        repo, wt = montar(d)
        env = {"CLAUDE_PROJECT_DIR": str(repo)}
        sh("bash .workflow/phase.sh set build", cwd=wt, env=env)
        assert (wt / ".workflow" / ".phase.json").exists(), "no se escribió en el worktree"
        assert not (repo / ".workflow" / ".phase.json").exists(), "se escribió en el principal"


# ── Legibilidad de la colisión ───────────────────────────────────────────────

def caso_registra_worktree_y_branch():
    """Sin saber quién puso la fase, una heredada es indistinguible de la propia."""
    with tempfile.TemporaryDirectory() as d:
        repo, _ = montar(d)
        sh("bash .workflow/phase.sh set build", cwd=repo)
        estado = json.loads((repo / ".workflow" / ".phase.json").read_text(encoding="utf-8"))
        for clave in ("worktree", "branch", "pid", "fase", "politica_escritura"):
            assert clave in estado, f"falta '{clave}' en el estado: {estado}"
        assert estado["branch"] == "main", estado


def caso_avisa_si_la_puso_otro_worktree():
    """Dos sesiones en el mismo estado se pisan: hay que decirlo, no adivinarlo."""
    with tempfile.TemporaryDirectory() as d:
        repo, _ = montar(d)
        sh("bash .workflow/phase.sh set build", cwd=repo)
        p = repo / ".workflow" / ".phase.json"
        estado = json.loads(p.read_text(encoding="utf-8"))
        estado["worktree"] = "/otro/sitio"
        p.write_text(json.dumps(estado), encoding="utf-8")
        salida = fase(repo)
        assert "otro worktree" in salida and "/otro/sitio" in salida, salida
        r = sh("bash .workflow/phase.sh set review", cwd=repo)
        assert "otra sesión" in r.stdout, r.stdout


# ── El riesgo opuesto ────────────────────────────────────────────────────────

def caso_no_salta_a_otro_repositorio():
    """Si el cwd es otro repo, manda CLAUDE_PROJECT_DIR: un hook apuntando al repo
    de al lado deja pasar todo, y eso es peor que el candado compartido."""
    with tempfile.TemporaryDirectory() as d:
        repo, _ = montar(d)
        ajeno = Path(d) / "ajeno"
        ajeno.mkdir()
        sh("git init -q -b main . && git config user.email t@t.t && git config user.name t "
           "&& git commit -q --allow-empty -m x", cwd=ajeno)
        lib = PROYECTO / ".claude" / "hooks" / "lib-root.sh"
        r = sh(f"bash -c '. \"{lib}\"; wf_root'", cwd=ajeno,
               env={"CLAUDE_PROJECT_DIR": str(repo)})
        resuelto = r.stdout.strip()
        assert resuelto == str(Path(repo).resolve()), \
            f"resolvió a un repositorio ajeno: {resuelto}"


def caso_sin_claude_project_dir():
    """Fuera de Claude Code (CI, terminal) sigue funcionando con el worktree."""
    with tempfile.TemporaryDirectory() as d:
        repo, wt = montar(d)
        env = {"CLAUDE_PROJECT_DIR": ""}
        sh("bash .workflow/phase.sh set build", cwd=wt, env=env)
        assert "build" in fase(wt, env), fase(wt, env)
        assert "Sin fase" in fase(repo, env), fase(repo, env)


CASOS = [
    caso_worktrees_independientes,
    caso_el_worktree_no_pisa_al_principal,
    caso_clear_no_cruza,
    caso_archivo_en_cada_worktree,
    caso_registra_worktree_y_branch,
    caso_avisa_si_la_puso_otro_worktree,
    caso_no_salta_a_otro_repositorio,
    caso_sin_claude_project_dir,
]


def main():
    fallos = 0
    for caso in CASOS:
        try:
            caso()
            print(f"  ✓ {caso.__name__} — {(caso.__doc__ or '').strip().splitlines()[0]}")
        except AssertionError as exc:
            fallos += 1
            print(f"  ✗ {caso.__name__}: {str(exc)[:300]}")
    print()
    if fallos:
        print(f"❌ {fallos} de {len(CASOS)} casos fallaron.")
        return 1
    print(f"✓ {len(CASOS)} casos en verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

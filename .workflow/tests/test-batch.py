#!/usr/bin/env python3
"""Regresión de batch.sh — el orquestador desatendido.

Es la pieza más peligrosa del repositorio: N agentes escribiendo código y abriendo
PRs sin nadie mirando. El riesgo que importa no es que falle, es que **corra sin
estar autorizado**, así que esos casos van primero y son los más.

El segundo riesgo es que un fallo se pierda: si un plan revienta y el resumen dice
"3 con PR", el humano se enteraría revisando PRs que no existen.

`claude` y `gh` se reemplazan por stubs. Lo que se prueba es la orquestación
—worktree por plan, aislamiento, resumen, códigos de salida—, no el modelo.

    python3 .workflow/tests/test-batch.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PROYECTO = RAIZ.parent
CONF = "delivery" + ".conf"          # partido: la ruta literal está protegida

SCRIPTS = ("batch.sh", "ship.sh", "pr-body.py", "findings.py", "check-regression.py",
           "verify.sh", "phase.sh", "check-migrations.py", "audit-deps.sh")

STUB_CLAUDE = """#!/usr/bin/env bash
# Simula un agente que implementa el plan, escribe su test y commitea.
PLAN=""
for a in "$@"; do case "$a" in /build*) PLAN="${a#/build }";; esac; done
SLUG=$(basename "$PLAN" .md); SLUG="${SLUG#[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-}"
if [ "$SLUG" = "revienta" ]; then echo "[stub] fallo deliberado" >&2; exit 1; fi
mkdir -p tests
printf '#!/usr/bin/env bash\\necho %s\\n' "$SLUG" > "src-$SLUG.sh"
printf '#!/usr/bin/env bash\\n[ "$(bash src-%s.sh)" = "%s" ] || exit 1\\n' "$SLUG" "$SLUG" \\
  > "tests/test-$SLUG.sh"
git add "src-$SLUG.sh" "tests/test-$SLUG.sh"
git commit -q -m "feat($SLUG): implementado por el plan"
echo "[stub claude] $SLUG implementado y commiteado"
"""

STUB_GH = """#!/usr/bin/env bash
[ "$1" = "pr" ] && { echo "https://github.com/fake/repo/pull/7"; exit 0; }
exit 0
"""


def sh(cmd, cwd=None, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True,
                          check=False, env=e)


def montar(base, planes=("alpha", "beta"), con_remoto=True):
    repo = Path(base) / "repo"
    for d in (".workflow/tests", ".claude/hooks", "docs/plans", "bin"):
        (repo / d).mkdir(parents=True, exist_ok=True)
    for nombre in SCRIPTS:
        origen = RAIZ / nombre
        if origen.exists():
            (repo / ".workflow" / nombre).write_bytes(origen.read_bytes())
    (repo / ".claude" / "hooks" / "lib-root.sh").write_bytes(
        (PROYECTO / ".claude" / "hooks" / "lib-root.sh").read_bytes())

    (repo / "bin" / "claude").write_text(STUB_CLAUDE, encoding="utf-8")
    (repo / "bin" / "gh").write_text(STUB_GH, encoding="utf-8")
    for f in ("claude", "gh"):
        (repo / "bin" / f).chmod(0o755)

    (repo / ".gitignore").write_text(
        ".workflow/.last-verify.json\n.workflow/.phase.json\n"
        f".workflow/{CONF}\n.workflow/.batch-logs/\n.worktrees/\nbin/\n", encoding="utf-8")
    for nombre in planes:
        (repo / "docs" / "plans" / f"2026-09-09-{nombre}.md").write_text(
            f"# Plan {nombre}\n", encoding="utf-8")

    sh("git init -q -b develop . && git config user.email t@t.t && git config user.name t",
       cwd=repo)
    sh("git add -A && git commit -q -m base", cwd=repo)
    if con_remoto:
        remoto = Path(base) / "remote.git"
        sh(f"git init -q --bare '{remoto}'")
        sh(f"git remote add origin '{remoto}' && git push -q -u origin develop", cwd=repo)
    return repo


def autorizar(repo, **claves):
    """Escribe delivery.conf. Lo hace el test, no un comando: la ruta está protegida."""
    base = {"MODO_ENTREGA": "pr", "AGENTE_PUEDE_PUSHEAR": "si", "BATCH_HEADLESS": "si"}
    base.update(claves)
    (repo / ".workflow" / CONF).write_text(
        "".join(f"{k}={v}\n" for k, v in base.items()), encoding="utf-8")


def batch(repo, *args):
    ruta = f"{repo}/bin:" + os.environ["PATH"]
    r = sh("bash .workflow/batch.sh " + " ".join(args), cwd=repo, env={"PATH": ruta})
    return r.stdout + r.stderr, r.returncode


PLANES = "docs/plans/2026-09-09-alpha.md docs/plans/2026-09-09-beta.md"


# ── Autorización: lo que más importa ─────────────────────────────────────────

def caso_sin_conf_no_corre():
    """Sin delivery.conf no se ejecuta nada: N agentes solos no son el modo por defecto."""
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        salida, code = batch(repo, PLANES)
        assert code == 1 and "no está autorizado" in salida, salida
        assert not (repo / ".worktrees").exists(), "creó worktrees sin autorización"


def caso_modo_pr_solo_no_alcanza():
    """El modo PR autoriza entregar con un humano mirando, no correr desatendido."""
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        autorizar(repo, BATCH_HEADLESS="no")
        salida, code = batch(repo, PLANES)
        assert code == 1 and "no está autorizado" in salida, salida


def caso_headless_sin_push_no_alcanza():
    """Las tres claves, o ninguna: no hay combinación parcial que sirva."""
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        autorizar(repo, AGENTE_PUEDE_PUSHEAR="no")
        salida, code = batch(repo, PLANES)
        assert code == 1 and "no está autorizado" in salida, salida


def caso_dry_run_no_necesita_autorizacion():
    """Poder mirar qué haría sin autorizar nada es lo que hace revisable el resto."""
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        salida, code = batch(repo, "--dry-run", PLANES)
        assert code == 0, salida
        assert "alpha" in salida and "beta" in salida, salida
        assert "Nada ejecutado" in salida, salida
        assert not (repo / ".worktrees").exists(), "el dry-run creó worktrees"


# ── Orquestación ─────────────────────────────────────────────────────────────

def caso_un_pr_por_plan():
    """El camino feliz: cada plan acaba en su PR, y el resumen lo dice."""
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        autorizar(repo)
        salida, code = batch(repo, "--paralelo", "2", PLANES)
        assert code == 0, salida
        assert salida.count("PR abierto") >= 2, salida
        assert "2 con PR, 0 fallando" in salida, salida


def caso_branch_por_plan():
    """Cada plan trabaja en su propia branch, sin pisarse."""
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        autorizar(repo)
        batch(repo, PLANES)
        ramas = sh("git branch --format='%(refname:short)'", cwd=repo).stdout
        assert "feature/alpha" in ramas and "feature/beta" in ramas, ramas


def caso_worktree_se_limpia_al_terminar_bien():
    """Un worktree que ya está en el remoto no tiene por qué quedarse."""
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        autorizar(repo)
        batch(repo, PLANES)
        lista = sh("git worktree list", cwd=repo).stdout
        assert "alpha" not in lista and "beta" not in lista, lista


def caso_un_fallo_no_se_pierde():
    """Si un plan revienta, el resumen lo dice y el exit code no es 0."""
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d, planes=("alpha", "revienta"))
        autorizar(repo)
        salida, code = batch(
            repo, "docs/plans/2026-09-09-alpha.md docs/plans/2026-09-09-revienta.md")
        assert code == 1, salida
        assert "FALLO-BUILD" in salida, salida
        assert "1 con PR, 1 fallando" in salida, salida


def caso_worktree_del_fallo_se_queda():
    """Borrar el worktree de un fallo sería borrar la evidencia de por qué falló."""
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d, planes=("revienta",))
        autorizar(repo)
        batch(repo, "docs/plans/2026-09-09-revienta.md")
        assert (repo / ".worktrees" / "revienta").exists(), "se llevó la evidencia"


def caso_branch_existente_se_salta():
    """Reejecutar no puede pisar trabajo ya empezado."""
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        autorizar(repo)
        sh("git branch feature/alpha", cwd=repo)
        salida, _ = batch(repo, PLANES)
        assert "la branch ya existía" in salida, salida


def caso_plan_inexistente_para_antes_de_tocar_nada():
    """Un plan mal escrito se detecta antes de crear worktrees, no a mitad."""
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        autorizar(repo)
        salida, code = batch(repo, "docs/plans/no-existe.md")
        assert code == 1 and "No existe el plan" in salida, salida
        assert not (repo / ".worktrees").exists(), salida


def caso_tope_de_paralelismo():
    """El cuello de botella es la revisión humana: N PRs sin revisar no son progreso."""
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        autorizar(repo)
        salida, _ = batch(repo, "--paralelo", "9", "--dry-run", PLANES)
        assert "lo limito a 4" in salida, salida


def caso_base_inexistente():
    """Una base que no existe se dice, no se inventa."""
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        autorizar(repo)
        salida, code = batch(repo, "--base", "no-existe", PLANES)
        assert code == 1 and "no existe" in salida, salida


CASOS = [
    caso_sin_conf_no_corre,
    caso_modo_pr_solo_no_alcanza,
    caso_headless_sin_push_no_alcanza,
    caso_dry_run_no_necesita_autorizacion,
    caso_un_pr_por_plan,
    caso_branch_por_plan,
    caso_worktree_se_limpia_al_terminar_bien,
    caso_un_fallo_no_se_pierde,
    caso_worktree_del_fallo_se_queda,
    caso_branch_existente_se_salta,
    caso_plan_inexistente_para_antes_de_tocar_nada,
    caso_tope_de_paralelismo,
    caso_base_inexistente,
]


def main():
    fallos = 0
    for caso in CASOS:
        try:
            caso()
            print(f"  ✓ {caso.__name__} — {(caso.__doc__ or '').strip().splitlines()[0]}")
        except AssertionError as exc:
            fallos += 1
            print(f"  ✗ {caso.__name__}: {str(exc)[:500]}")
    print()
    if fallos:
        print(f"❌ {fallos} de {len(CASOS)} casos fallaron.")
        return 1
    print(f"✓ {len(CASOS)} casos en verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

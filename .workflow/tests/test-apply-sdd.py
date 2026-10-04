#!/usr/bin/env python3
"""Regresión: apply-sdd.sh overlaya el workflow sin pisar verify.conf ni el norte.

python3 .workflow/tests/test-apply-sdd.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
SCRIPT = RAIZ / "apply-sdd.sh"
NORTE = "programar musicos sin doble asignacion."


def _env():
    e = dict(os.environ)
    e.pop("CLAUDE_PROJECT_DIR", None)
    return e


def sh(cwd, *args, check=True):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check, env=_env())


def montar(base):
    proy = Path(base) / "viejo"
    proy.mkdir()
    sh(proy, "git", "init", "-q", "-b", "main", ".")
    sh(proy, "git", "config", "user.email", "t@t.t")
    sh(proy, "git", "config", "user.name", "t")
    (proy / ".workflow").mkdir()
    (proy / ".workflow" / "verify.conf").write_text("UNIQUE_VERIFY_TOKEN=keep-me\n", encoding="utf-8")
    (proy / ".workflow" / "delivery.conf").write_text("MODO_ENTREGA=local\n", encoding="utf-8")
    (proy / "CLAUDE.md").write_text(
        f"# Gobernanza\n\n**Este sistema existe para:** {NORTE}\n\n---\nprosa larga del workflow viejo\n",
        encoding="utf-8",
    )
    (proy / "app.py").write_text("x = 1\n", encoding="utf-8")
    sh(proy, "git", "add", "-A")
    sh(proy, "git", "commit", "-qm", "chore: seed")
    return proy


def apply(proy, *flags):
    r = subprocess.run(
        ["bash", str(SCRIPT), str(proy), *flags],
        capture_output=True,
        text=True,
        check=False,
        env=_env(),
    )
    return r.stdout + r.stderr, r.returncode


def test_v15_dry_run_no_escribe():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        out, rc = apply(proy, "--dry-run")
        assert rc == 0, out
        assert "dry-run" in out
        assert not (proy / "FORMAT.md").exists()
        assert "prosa larga" in (proy / "CLAUDE.md").read_text(encoding="utf-8")


def test_v15_overlay_preserva_conf_y_norte():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        out, rc = apply(proy)
        assert rc == 0, out
        assert (proy / ".claude" / "commands" / "spec.md").is_file()
        assert (proy / ".claude" / "commands" / "check.md").is_file()
        assert (proy / "FORMAT.md").is_file()
        verify = (proy / ".workflow" / "verify.conf").read_text(encoding="utf-8")
        assert "UNIQUE_VERIFY_TOKEN=keep-me" in verify
        delivery = (proy / ".workflow" / "delivery.conf").read_text(encoding="utf-8")
        assert "MODO_ENTREGA=local" in delivery
        spec = (proy / "SPEC.md").read_text(encoding="utf-8")
        assert "programar musicos" in spec
        assert "Andamiaje para construir" not in spec
        claude = (proy / "CLAUDE.md").read_text(encoding="utf-8")
        assert "[pendiente" in claude
        assert (proy / ".claude" / "CLAUDE.md.pre-sdd").is_file()
        assert (proy / ".claude" / "sdd-distill-prompt.txt").is_file()
        branch = sh(proy, "git", "branch", "--show-current").stdout.strip()
        assert branch == "chore/sdd-workflow"
        assert (proy / ".git" / "hooks" / "pre-commit").is_file()


def test_v15_no_pisa_spec_con_g():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        (proy / "SPEC.md").write_text(
            "# SPEC\n\n## §G GOAL\nel producto ya tenia norte\n\n## §M MODE\nspec\n",
            encoding="utf-8",
        )
        sh(proy, "git", "add", "SPEC.md")
        sh(proy, "git", "commit", "-qm", "docs: spec previa")
        out, rc = apply(proy)
        assert rc == 0, out
        spec = (proy / "SPEC.md").read_text(encoding="utf-8")
        assert "el producto ya tenia norte" in spec
        assert "programar musicos" not in spec


def test_v15_feature_para():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        sh(proy, "git", "checkout", "-qb", "test/invariantes-spec")
        out, rc = apply(proy)
        assert rc != 0, out
        assert "no en main/develop" in out
        assert not (proy / "FORMAT.md").exists()
        assert sh(proy, "git", "branch", "--show-current").stdout.strip() == "test/invariantes-spec"


def test_v15_dry_run_feature_tambien_para():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        sh(proy, "git", "checkout", "-qb", "feature/foo")
        out, rc = apply(proy, "--dry-run")
        assert rc != 0, out
        assert "no en main/develop" in out


def test_v15_reusa_branch_existente():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        out, rc = apply(proy)
        assert rc == 0, out
        sh(proy, "git", "add", "-A")
        sh(proy, "git", "-c", "core.hooksPath=/dev/null", "commit", "-qm", "chore: primer overlay")
        sh(proy, "git", "checkout", "-q", "main")
        out, rc = apply(proy)
        assert rc == 0, out
        assert "ya existe" in out or "checkout" in out
        assert sh(proy, "git", "branch", "--show-current").stdout.strip() == "chore/sdd-workflow"


def test_v15_no_pisa_presdd():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        (proy / ".claude").mkdir()
        (proy / ".claude" / "CLAUDE.md.pre-sdd").write_text("NORTE_VIEJO_UNICO\n", encoding="utf-8")
        sh(proy, "git", "add", "-A")
        sh(proy, "git", "commit", "-qm", "chore: backup previo")
        out, rc = apply(proy)
        assert rc == 0, out
        assert "no se pisa" in out
        assert (proy / ".claude" / "CLAUDE.md.pre-sdd").read_text(encoding="utf-8") == "NORTE_VIEJO_UNICO\n"


def test_v15_skip_branch_en_feature():
    with tempfile.TemporaryDirectory() as d:
        proy = montar(d)
        sh(proy, "git", "checkout", "-qb", "feature/ok")
        out, rc = apply(proy, "--skip-branch")
        assert rc == 0, out
        assert (proy / "FORMAT.md").is_file()
        assert sh(proy, "git", "branch", "--show-current").stdout.strip() == "feature/ok"


CASOS = [
    test_v15_dry_run_no_escribe,
    test_v15_overlay_preserva_conf_y_norte,
    test_v15_no_pisa_spec_con_g,
    test_v15_feature_para,
    test_v15_dry_run_feature_tambien_para,
    test_v15_reusa_branch_existente,
    test_v15_no_pisa_presdd,
    test_v15_skip_branch_en_feature,
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

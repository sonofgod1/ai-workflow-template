#!/usr/bin/env python3
"""Regresión: la política `spec` deja escribir SPEC.md y bloquea código.

python3 .workflow/tests/test-spec-policy.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "write-guard.py"
PHASE = ROOT / "phase.sh"


def sh(repo, cmd, env=None):
    e = dict(os.environ)
    e.pop("CLAUDE_PROJECT_DIR", None)
    if env:
        e.update(env)
    r = subprocess.run(cmd, shell=True, cwd=repo, env=e, capture_output=True, text=True, check=False)
    return r.stdout + r.stderr, r.returncode


def montar(d):
    repo = Path(d)
    (repo / ".workflow").mkdir()
    (repo / ".claude" / "hooks").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "src").mkdir()
    os.symlink(GUARD, repo / ".workflow" / "write-guard.py")
    os.symlink(PHASE, repo / ".workflow" / "phase.sh")
    lib = ROOT / ".claude" / "hooks" / "lib-root.sh"
    if lib.exists():
        os.symlink(lib, repo / ".claude" / "hooks" / "lib-root.sh")
    (repo / "SPEC.md").write_text("# SPEC\n", encoding="utf-8")
    (repo / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    return repo


def check(repo, path):
    payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(repo / path)}})
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
    r = subprocess.run(
        [sys.executable, str(GUARD), "check"],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        cwd=repo,
        check=False,
    )
    return r.returncode, r.stderr


def caso_spec_permite_spec_md():
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        out, code = sh(repo, "bash .workflow/phase.sh set spec")
        assert code == 0, out
        assert "SPEC.md" in out, out
        rc, err = check(repo, "SPEC.md")
        assert rc == 0, err


def caso_spec_permite_docs():
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        sh(repo, "bash .workflow/phase.sh set spec")
        rc, err = check(repo, "docs/discovery.md")
        assert rc == 0, err


def caso_spec_bloquea_codigo():
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        sh(repo, "bash .workflow/phase.sh set spec")
        rc, err = check(repo, "src/app.py")
        assert rc == 2, f"debía bloquear código, code={rc} err={err}"
        assert "SPEC.md" in err, err


def caso_fase_spec_existe():
    with tempfile.TemporaryDirectory() as d:
        repo = montar(d)
        out, code = sh(repo, "bash .workflow/phase.sh set spec")
        assert code == 0 and "spec" in out, out
        out, code = sh(repo, "bash .workflow/phase.sh set check")
        assert code == 0 and "docs" in out, out
        out, code = sh(repo, "bash .workflow/phase.sh set explore")
        assert code == 0 and "full" in out, out


def caso_claude_md_es_corto():
    n = len((ROOT.parent / "CLAUDE.md").read_text(encoding="utf-8").splitlines())
    assert n <= 220, f"CLAUDE.md tiene {n} líneas; V1 pide ≤ ~200 always-on"


CASOS = [
    caso_spec_permite_spec_md,
    caso_spec_permite_docs,
    caso_spec_bloquea_codigo,
    caso_fase_spec_existe,
    caso_claude_md_es_corto,
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
    if fallos:
        print(f"❌ {fallos} de {len(CASOS)} casos fallaron.")
        return 1
    print(f"✓ {len(CASOS)} casos en verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

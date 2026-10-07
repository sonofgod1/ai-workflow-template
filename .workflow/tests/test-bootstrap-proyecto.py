#!/usr/bin/env python3
"""Regresión V17: una copia de la plantilla no hereda su spec ni su verify.conf.

python3 .workflow/tests/test-bootstrap-proyecto.py
"""

import os
import subprocess
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
SCRIPT = RAIZ / ".workflow" / "bootstrap-proyecto.py"
CMD = RAIZ / ".claude" / "commands"


def _env():
    entorno = dict(os.environ)
    entorno.pop("CLAUDE_PROJECT_DIR", None)
    return entorno


def sh(cwd, *args, check=True):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check, env=_env())


def sembrar(base, *, remote=None, commits=1, spec=None, verify=None, marca=True):
    proy = Path(base) / "proy"
    proy.mkdir()
    (proy / ".workflow").mkdir()
    sh(proy, "git", "init", "-q", "-b", "main", ".")
    sh(proy, "git", "config", "user.email", "t@t.t")
    sh(proy, "git", "config", "user.name", "t")
    if spec is None:
        spec = (RAIZ / "SPEC.md").read_text(encoding="utf-8")
    (proy / "SPEC.md").write_text(spec, encoding="utf-8")
    if verify is None:
        verify = (RAIZ / ".workflow" / "verify.conf").read_text(encoding="utf-8")
    if verify is not False:
        (proy / ".workflow" / "verify.conf").write_text(verify, encoding="utf-8")
    if marca:
        (proy / ".workflow" / "es-plantilla").write_text(
            (RAIZ / ".workflow" / "es-plantilla").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
    sh(proy, "git", "add", "-A")
    sh(proy, "git", "commit", "-qm", "chore: seed")
    for _ in range(commits - 1):
        (proy / "nota.txt").write_text("otro\n", encoding="utf-8")
        sh(proy, "git", "add", "nota.txt")
        sh(proy, "git", "commit", "-qm", "chore: otro")
    if remote:
        sh(proy, "git", "remote", "add", "origin", remote)
    return proy


def correr(proy, *flags):
    resultado = subprocess.run(
        ["python3", str(SCRIPT), *flags],
        cwd=proy,
        capture_output=True,
        text=True,
        check=False,
        env=_env(),
    )
    return resultado.stdout.strip(), resultado.stderr, resultado.returncode


def test_v17_copia_reemplaza_spec_y_verify():
    with tempfile.TemporaryDirectory() as d:
        proy = sembrar(d, remote="git@github.com:alguien/mi-proyecto.git")
        antes = (proy / "SPEC.md").read_text(encoding="utf-8")
        palabra, err, rc = correr(proy)
        assert rc == 0, err
        assert palabra == "copia"
        spec = (proy / "SPEC.md").read_text(encoding="utf-8")
        assert spec != antes
        assert "[pendiente" in spec
        assert "Andamiaje para construir" not in spec
        assert not (proy / ".workflow" / "verify.conf").exists()
        assert not (proy / ".workflow" / "es-plantilla").exists()


def test_v17_detect_no_escribe():
    with tempfile.TemporaryDirectory() as d:
        proy = sembrar(d, remote="git@github.com:alguien/mi-proyecto.git")
        antes = (proy / "SPEC.md").read_text(encoding="utf-8")
        palabra, err, rc = correr(proy, "--detect")
        assert rc == 0, err
        assert palabra == "copia"
        assert (proy / "SPEC.md").read_text(encoding="utf-8") == antes
        assert (proy / ".workflow" / "verify.conf").is_file()
        assert (proy / ".workflow" / "es-plantilla").is_file()


def test_v17_remote_de_la_plantilla_no_escribe():
    with tempfile.TemporaryDirectory() as d:
        proy = sembrar(d, remote="git@github.com:sonofgod1/ai-workflow-template.git")
        antes = (proy / "SPEC.md").read_text(encoding="utf-8")
        palabra, err, rc = correr(proy)
        assert rc == 0, err
        assert palabra == "plantilla"
        assert (proy / "SPEC.md").read_text(encoding="utf-8") == antes
        assert (proy / ".workflow" / "verify.conf").is_file()
        assert (proy / ".workflow" / "es-plantilla").is_file()


def test_v17_force_en_la_plantilla_rechaza():
    with tempfile.TemporaryDirectory() as d:
        proy = sembrar(d, remote="https://github.com/sonofgod1/ai-workflow-template.git")
        antes = (proy / "SPEC.md").read_text(encoding="utf-8")
        palabra, err, rc = correr(proy, "--force")
        assert rc == 2, (palabra, err)
        assert "plantilla" in err
        assert (proy / "SPEC.md").read_text(encoding="utf-8") == antes


def test_v17_historia_larga_sin_remote_es_plantilla():
    with tempfile.TemporaryDirectory() as d:
        proy = sembrar(d, commits=2)
        antes = (proy / "SPEC.md").read_text(encoding="utf-8")
        palabra, err, rc = correr(proy)
        assert rc == 0, err
        assert palabra == "plantilla"
        assert (proy / "SPEC.md").read_text(encoding="utf-8") == antes


def test_v17_spec_de_producto_no_se_pisa():
    with tempfile.TemporaryDirectory() as d:
        spec = (
            (RAIZ / "SPEC.md")
            .read_text(encoding="utf-8")
            .replace(
                "Andamiaje para construir sistemas digitales con agentes",
                "programar musicos sin doble asignacion",
            )
        )
        proy = sembrar(
            d,
            remote="git@github.com:alguien/mi-proyecto.git",
            spec=spec,
            verify="UNIQUE_VERIFY_TOKEN=keep-me\n",
        )
        palabra, err, rc = correr(proy)
        assert rc == 0, err
        assert palabra == "proyecto"
        assert "programar musicos" in (proy / "SPEC.md").read_text(encoding="utf-8")
        assert "UNIQUE_VERIFY_TOKEN=keep-me" in (proy / ".workflow" / "verify.conf").read_text(
            encoding="utf-8"
        )
        assert not (proy / ".workflow" / "es-plantilla").exists()


def test_v17_segunda_corrida_es_proyecto():
    with tempfile.TemporaryDirectory() as d:
        proy = sembrar(d, remote="git@github.com:alguien/mi-proyecto.git")
        correr(proy)
        palabra, err, rc = correr(proy)
        assert rc == 0, err
        assert palabra == "proyecto"
        assert "[pendiente" in (proy / "SPEC.md").read_text(encoding="utf-8")


def test_v17_comandos_entregan_el_arranque():
    spec = (CMD / "spec.md").read_text(encoding="utf-8")
    discovery = (CMD / "discovery.md").read_text(encoding="utf-8")
    architect = (CMD / "architect.md").read_text(encoding="utf-8")
    build = (CMD / "build.md").read_text(encoding="utf-8")
    feature = (CMD / "feature.md").read_text(encoding="utf-8")
    assert "bootstrap-proyecto.py" in spec
    assert "NEW" in spec
    assert "[pendiente" in spec
    assert "¿Qué problema resuelve esto, en una oración, para quién?" in discovery
    assert "bootstrap-proyecto.py" in discovery
    assert "bootstrap-proyecto.py" in architect
    assert "[pendiente" in architect
    assert "bootstrap-proyecto.py" in build
    assert "[pendiente" in build
    assert "bootstrap-proyecto.py" in feature
    assert "graphify-declinado" in discovery
    assert "primer `/build`" in discovery
    assert "graphify-declinado" in build
    spec_txt = (RAIZ / "SPEC.md").read_text(encoding="utf-8")
    assert "Graphify no es paso 0." in spec_txt
    apply = (RAIZ / "apply-sdd.sh").read_text(encoding="utf-8")
    assert "es-plantilla" in apply
    sync = (RAIZ / "sync-workflow.sh").read_text(encoding="utf-8")
    assert "bootstrap-proyecto.py" in sync


CASOS = [
    test_v17_copia_reemplaza_spec_y_verify,
    test_v17_detect_no_escribe,
    test_v17_remote_de_la_plantilla_no_escribe,
    test_v17_force_en_la_plantilla_rechaza,
    test_v17_historia_larga_sin_remote_es_plantilla,
    test_v17_spec_de_producto_no_se_pisa,
    test_v17_segunda_corrida_es_proyecto,
    test_v17_comandos_entregan_el_arranque,
]


def main():
    fallos = 0
    for caso in CASOS:
        try:
            caso()
            print(f"ok  {caso.__name__}")
        except Exception as exc:
            fallos += 1
            print(f"FAIL {caso.__name__}: {exc}")
    if fallos:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

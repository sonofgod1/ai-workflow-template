#!/usr/bin/env python3
"""Regresión V17/V18: una copia no hereda spec, verify.conf ni hallazgos.

Los fixtures viven en este archivo. Leerlos del checkout rompe en cuanto
bootstrap borra verify.conf y es-plantilla, que es justo el caso que CI corre
en un proyecto nuevo.

python3 .workflow/tests/test-bootstrap-proyecto.py
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
SCRIPT = RAIZ / ".workflow" / "bootstrap-proyecto.py"
CMD = RAIZ / ".claude" / "commands"
FINDINGS = RAIZ / ".workflow" / "findings.py"

GOAL = "Andamiaje para construir sistemas digitales con agentes"
MARCA_TXT = f"repo=ai-workflow-template\ngoal={GOAL}\n"
SPEC_PLANTILLA = f"""# SPEC

## §G GOAL
{GOAL}: una spec viva manda,
el código se verifica contra ella.

## §M MODE
spec

## §C CONSTRAINTS
- Graphify no es paso 0.

## §I INTERFACES
- cmd: bootstrap

## §V INVARIANTS
V1: x

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
VERIFY_PLANTILLA = (
    '# Contrato de verificación de la plantilla.\nVERIFY_STEPS=(\n  "tests-andamiaje:true"\n)\n'
)
COMMIT_AJENO = "e0d1cbd90910f25a08bd62fc3241b95581bdcffe"


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
        spec = SPEC_PLANTILLA
    (proy / "SPEC.md").write_text(spec, encoding="utf-8")
    if verify is None:
        verify = VERIFY_PLANTILLA
    if verify is not False:
        (proy / ".workflow" / "verify.conf").write_text(verify, encoding="utf-8")
    if marca:
        (proy / ".workflow" / "es-plantilla").write_text(MARCA_TXT, encoding="utf-8")
    sh(proy, "git", "add", "-A")
    sh(proy, "git", "commit", "-qm", "chore: seed")
    for _ in range(commits - 1):
        (proy / "nota.txt").write_text("otro\n", encoding="utf-8")
        sh(proy, "git", "add", "nota.txt")
        sh(proy, "git", "commit", "-qm", "chore: otro")
    if remote:
        sh(proy, "git", "remote", "add", "origin", remote)
    return proy


def poner_indice(proy, hallazgos):
    docs = proy / "docs"
    (docs / "reviews").mkdir(parents=True)
    (docs / "findings.json").write_text(
        json.dumps({"version": 1, "hallazgos": hallazgos}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (docs / "reviews" / "decisiones.md").write_text("viejo\n", encoding="utf-8")


def leer_indice(proy):
    return json.loads((proy / "docs" / "findings.json").read_text(encoding="utf-8"))


def hallazgo(commit, hid="I1", *, exento=False):
    fila = {
        "id": hid,
        "severidad": "important",
        "titulo": "hallazgo de la plantilla",
        "estado": "resuelto",
        "commit": commit,
    }
    if exento:
        fila["test"] = {"estado": "exento", "razon": "fixture del test"}
    return fila


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


def indice_pasa_ci(proy):
    r = subprocess.run(
        ["python3", str(FINDINGS), "validate", "--exigir-test"],
        cwd=proy,
        capture_output=True,
        text=True,
        check=False,
        env=_env(),
    )
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run(
        ["python3", str(FINDINGS), "decisiones", "--check"],
        cwd=proy,
        capture_output=True,
        text=True,
        check=False,
        env=_env(),
    )
    assert r.returncode == 0, r.stdout + r.stderr


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
        spec = SPEC_PLANTILLA.replace(
            GOAL,
            "programar musicos sin doble asignacion",
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
    # Esa frase vive en el SPEC de la plantilla. Una copia ya lo reemplazó.
    if (RAIZ / ".workflow" / "es-plantilla").is_file():
        spec_txt = (RAIZ / "SPEC.md").read_text(encoding="utf-8")
        assert "Graphify no es paso 0." in spec_txt
    apply = (RAIZ / "apply-sdd.sh").read_text(encoding="utf-8")
    assert "es-plantilla" in apply
    sync = (RAIZ / "sync-workflow.sh").read_text(encoding="utf-8")
    assert "bootstrap-proyecto.py" in sync


def test_v18_copia_vacía_hallazgos():
    with tempfile.TemporaryDirectory() as d:
        proy = sembrar(d, remote="git@github.com:alguien/mi-proyecto.git")
        poner_indice(proy, [hallazgo(COMMIT_AJENO)])
        palabra, err, rc = correr(proy)
        assert rc == 0, err
        assert palabra == "copia"
        assert leer_indice(proy)["hallazgos"] == []
        assert "Sin hallazgos registrados todavía." in (
            proy / "docs" / "reviews" / "decisiones.md"
        ).read_text(encoding="utf-8")
        indice_pasa_ci(proy)


def test_v18_proyecto_quita_commit_ajeno_y_conserva_el_propio():
    with tempfile.TemporaryDirectory() as d:
        proy = sembrar(d, remote="git@github.com:alguien/mi-proyecto.git")
        correr(proy)
        propio = sh(proy, "git", "rev-parse", "HEAD").stdout.strip()
        poner_indice(proy, [hallazgo(COMMIT_AJENO), hallazgo(propio, "I2", exento=True)])
        palabra, err, rc = correr(proy)
        assert rc == 0, err
        assert palabra == "proyecto"
        ids = [h["id"] for h in leer_indice(proy)["hallazgos"]]
        assert ids == ["I2"]
        indice_pasa_ci(proy)


def test_v18_proyecto_conserva_indice_propio():
    with tempfile.TemporaryDirectory() as d:
        proy = sembrar(d, remote="git@github.com:alguien/mi-proyecto.git")
        correr(proy)
        propio = sh(proy, "git", "rev-parse", "HEAD").stdout.strip()
        poner_indice(proy, [hallazgo(propio, "B9")])
        palabra, err, rc = correr(proy)
        assert rc == 0, err
        assert palabra == "proyecto"
        assert leer_indice(proy)["hallazgos"][0]["commit"] == propio
        assert (proy / "docs" / "reviews" / "decisiones.md").read_text(encoding="utf-8") == "viejo\n"


def test_v18_plantilla_no_toca_hallazgos():
    with tempfile.TemporaryDirectory() as d:
        proy = sembrar(d, remote="git@github.com:sonofgod1/ai-workflow-template.git")
        poner_indice(proy, [hallazgo(COMMIT_AJENO)])
        palabra, err, rc = correr(proy)
        assert rc == 0, err
        assert palabra == "plantilla"
        assert leer_indice(proy)["hallazgos"][0]["commit"] == COMMIT_AJENO
        assert (proy / "docs" / "reviews" / "decisiones.md").read_text(encoding="utf-8") == "viejo\n"


CASOS = [
    test_v17_copia_reemplaza_spec_y_verify,
    test_v17_detect_no_escribe,
    test_v17_remote_de_la_plantilla_no_escribe,
    test_v17_force_en_la_plantilla_rechaza,
    test_v17_historia_larga_sin_remote_es_plantilla,
    test_v17_spec_de_producto_no_se_pisa,
    test_v17_segunda_corrida_es_proyecto,
    test_v17_comandos_entregan_el_arranque,
    test_v18_copia_vacía_hallazgos,
    test_v18_proyecto_quita_commit_ajeno_y_conserva_el_propio,
    test_v18_proyecto_conserva_indice_propio,
    test_v18_plantilla_no_toca_hallazgos,
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

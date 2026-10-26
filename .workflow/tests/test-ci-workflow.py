#!/usr/bin/env python3
"""ci.yml: la barrera no repite trabajo y frena los bloqueantes antes del release.

Sale de un proyecto consumidor (musicos, 2026-10-26): cada entrega corría el CI
completo cuatro veces (PR, push del merge, PR de release, push a main), y
`--sin-bloqueantes` solo miraba `github.ref`, así que un blocker abierto nunca
frenaba el PR hacia main y dejaba main en rojo después de cada release.

    python3 .workflow/tests/test-ci-workflow.py
"""

import os
import re
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
CI = (RAIZ / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")


def bloque_job(nombre):
    """Texto del job `nombre` hasta el siguiente job de primer nivel."""
    resto = CI[CI.index(f"\n  {nombre}:\n") + 1:]
    siguiente = re.search(r"\n  [a-z][\w-]*:\n", resto[1:])
    return resto[: siguiente.start() + 1] if siguiente else resto


def script_detect():
    """El `run:` del paso `check` de detect, sin la indentación del YAML."""
    job = bloque_job("detect")
    cuerpo = job.split("run: |\n", 1)[1].split("        shell: bash", 1)[0]
    return textwrap.dedent(cuerpo)


def correr_detect(archivos):
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        for ruta in archivos:
            (repo / ruta).parent.mkdir(parents=True, exist_ok=True)
            (repo / ruta).write_text("{}\n", encoding="utf-8")
        salida = repo / "github_output"
        salida.write_text("", encoding="utf-8")
        r = subprocess.run(
            ["bash", "-c", script_detect()],
            cwd=repo,
            env={**os.environ, "GITHUB_OUTPUT": str(salida)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 0, r.stderr
        return salida.read_text(encoding="utf-8")


def test_concurrency_cancela_solo_en_pr():
    """un push nuevo al PR cancela la corrida vieja; main/develop no se cancelan"""
    assert "\nconcurrency:\n" in CI
    assert "cancel-in-progress: ${{ github.event_name == 'pull_request' }}" in CI


def test_verificacion_no_se_repite_en_el_push_del_merge():
    """el push del merge de un PR salta verificacion; un push directo la corre"""
    job = bloque_job("verificacion")
    assert "github.event_name == 'pull_request'" in job
    assert "!startsWith(github.event.head_commit.message, 'Merge pull request')" in job


def test_bloqueantes_frenan_el_pr_hacia_main():
    """--sin-bloqueantes también aplica al PR con base main, no solo al push"""
    job = bloque_job("hallazgos")
    assert '"${{ github.base_ref }}" = "main"' in job
    assert "--sin-bloqueantes" in job


def test_cache_solo_con_manifiestos():
    """sin manifiestos no se pide caché: setup-* falla si el path no matchea nada"""
    out = correr_detect([])
    assert "pip_cache=" not in out, out
    assert "npm_cache=" not in out, out


def test_cache_en_monorepo():
    """encuentra los manifiestos en subcarpetas e ignora node_modules"""
    out = correr_detect(
        [
            "backend/requirements.txt",
            "backend/requirements-dev.txt",
            "frontend/package-lock.json",
            "frontend/node_modules/dep/package-lock.json",
        ]
    )
    assert "pip_cache=pip" in out, out
    assert "backend/requirements-dev.txt\nbackend/requirements.txt\n" in out, out
    assert "npm_cache=npm" in out, out
    assert "frontend/package-lock.json" in out, out
    assert "node_modules" not in out, out


def test_verificacion_usa_la_cache_detectada():
    """verificacion consume la caché que calculó detect"""
    job = bloque_job("verificacion")
    assert "cache: ${{ needs.detect.outputs.pip_cache }}" in job
    assert "cache-dependency-path: ${{ needs.detect.outputs.pip_deps }}" in job
    assert "cache: ${{ needs.detect.outputs.npm_cache }}" in job
    assert "cache-dependency-path: ${{ needs.detect.outputs.npm_deps }}" in job


CASOS = [
    test_concurrency_cancela_solo_en_pr,
    test_verificacion_no_se_repite_en_el_push_del_merge,
    test_bloqueantes_frenan_el_pr_hacia_main,
    test_cache_solo_con_manifiestos,
    test_cache_en_monorepo,
    test_verificacion_usa_la_cache_detectada,
]


def main():
    fallos = 0
    for caso in CASOS:
        try:
            caso()
            print(
                f"  ✓ {caso.__name__} — {(caso.__doc__ or '').strip().splitlines()[0] if caso.__doc__ else ''}"
            )
        except AssertionError as exc:
            fallos += 1
            print(f"  ✗ {caso.__name__}: {str(exc)[:500]}")
        except Exception as exc:
            fallos += 1
            print(f"  ✗ {caso.__name__}: {type(exc).__name__}: {exc}")
    print()
    if fallos:
        print(f"❌ {fallos} de {len(CASOS)} casos fallaron.")
        return 1
    print(f"✓ {len(CASOS)} casos en verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

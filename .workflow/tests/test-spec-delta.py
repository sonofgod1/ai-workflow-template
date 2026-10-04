#!/usr/bin/env python3
"""Regresión: spec actual vs §D (V11, V12, V13).

python3 .workflow/tests/test-spec-delta.py
"""

import importlib.util
import sys
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parent.parent
REPO = WORKFLOW.parent

SPEC = (REPO / "SPEC.md").read_text(encoding="utf-8")
FORMAT = (REPO / "FORMAT.md").read_text(encoding="utf-8")
CMD = REPO / ".claude" / "commands"

SECCIONES = [
    "§G GOAL",
    "§M MODE",
    "§C CONSTRAINTS",
    "§I INTERFACES",
    "§V INVARIANTS",
    "§T TASKS",
    "§B BUGS",
    "§D DELTA",
]


def _pr_body():
    spec = importlib.util.spec_from_file_location("pr_body", WORKFLOW / "pr-body.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cmd(name):
    return (CMD / name).read_text(encoding="utf-8")


def test_v2_orden_incluye_delta():
    pos = [SPEC.index(f"## {h}") for h in SECCIONES]
    assert pos == sorted(pos), f"orden roto: {pos}"
    for h in SECCIONES:
        assert f"## {h}" in FORMAT


def test_v11_spec_escribe_delta_no_inplace():
    spec = _cmd("spec.md")
    feat = _cmd("feature.md")
    assert "§D" in spec and "ADDED" in spec and "MODIFIED" in spec
    assert "aún no es verdad" in spec or "no es verdad" in spec
    assert (
        "No reescribís §I/§V enteros" in spec
        or "no reescribís §I/§V" in spec.lower()
        or "⊥ reescribir" in spec
    )
    assert "§D" in feat and "ADDED" in feat
    assert "ACTUAL VS DELTA" in FORMAT
    assert "ADDED" in FORMAT and "REMOVED" in FORMAT
    assert "⊥ reescribir §I/§V enteros" in FORMAT


def test_v12_check_ignora_delta_abierto():
    check = _cmd("check.md")
    assert "No marques MISSING" in check or "no es MISSING" in check
    assert "solo existen como `ADDED`" in check or "ADDED" in check
    assert "STALE" in check
    assert "faltó el fold" in check
    assert "## CHECK §D" in check
    assert "No son VIOLATE ni MISSING" in check


def test_v13_build_folda_al_x():
    build = _cmd("build.md")
    assert "fold" in build.lower()
    assert "§D" in build
    assert "`?`" in build or "tiene `?`" in build
    assert "fold de §D" in FORMAT or "Fold" in FORMAT
    assert "Sin fold no hay `x`" in FORMAT


def test_v11_parser_vacio_y_filas():
    pb = _pr_body()
    vacio = """## §D DELTA
id|op|target|change|cites
-|-|-|-|-
"""
    assert pb.spec_delta_rows(vacio) == []
    assert pb.spec_delta_rows("# SPEC\n") == []

    con = """## §D DELTA
id|op|target|change|cites
D1|ADDED|§I|api: POST /x → 200 {id}|T2
D2|MODIFIED|§V.5|/check ignora §D|T2
D3|REMOVED|§I|cmd: `foo legacy`|T2
"""
    rows = pb.spec_delta_rows(con)
    assert [r["id"] for r in rows] == ["D1", "D2", "D3"]
    assert rows[0]["op"] == "ADDED"
    assert rows[1]["target"] == "§V.5"
    assert rows[2]["cites"] == "T2"


def test_v12_pregunta_no_se_folda():
    assert "`change` con `?`" in FORMAT or "con `?`" in FORMAT


CASOS = [
    test_v2_orden_incluye_delta,
    test_v11_spec_escribe_delta_no_inplace,
    test_v12_check_ignora_delta_abierto,
    test_v13_build_folda_al_x,
    test_v11_parser_vacio_y_filas,
    test_v12_pregunta_no_se_folda,
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

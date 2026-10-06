#!/usr/bin/env python3
"""Regresión V14 (verify.sh certifica) y V16 (check es el script, acotado a T<n>).

python3 .workflow/tests/test-spec-auditor.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1].parent
CMD = REPO / ".claude" / "commands"
CLAUDE = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
FORMAT = (REPO / "FORMAT.md").read_text(encoding="utf-8")
SPEC = (REPO / "SPEC.md").read_text(encoding="utf-8")
# SPEC.md y CLAUDE.md son del proyecto consumidor (el sync no los pisa): su V14/V16
# hablan de su producto, no del andamiaje. Las aserciones sobre ellos solo valen acá.
ES_PLANTILLA = "Andamiaje para construir sistemas digitales con agentes" in SPEC


def _cmd(name):
    return (CMD / name).read_text(encoding="utf-8")


def test_v14_build_no_invoca_check():
    build = _cmd("build.md")
    assert "No invocás `/check`" in build or "No invoques `/check`" in build
    assert "chat nuevo" not in build
    assert "modelo fuerte" not in build
    assert "/check --all" not in build
    assert "verify.sh" in build
    assert "/ship" in build


def test_v14_check_es_el_script():
    check = _cmd("check.md")
    assert "check-spec.py" in check
    assert "No leés el código" in check or "No leés" in check
    assert "chat nuevo" not in check
    assert "modelo fuerte" not in check
    assert "UNVERIFIABLE" in check


def test_v14_review_no_es_puerta():
    review = _cmd("review.md")
    assert "diff" in review
    assert "No es puerta de `/ship`" in review
    assert "chat nuevo" not in review
    assert "Este hilo construyó. No certifico." not in review


def test_v14_constitucion_y_formato():
    assert "## QUIÉN CERTIFICA" in FORMAT
    assert "check-spec.py" in FORMAT
    assert "CONSTRUCTOR ≠ AUDITOR" not in FORMAT
    if not ES_PLANTILLA:
        return
    assert "verify.sh` certifica" in CLAUDE or "`verify.sh` certifica" in CLAUDE
    assert "El que construye no certifica" not in CLAUDE
    assert "otro chat" not in CLAUDE.lower()
    assert "V14:" in SPEC


def test_v16_check_acepta_tarea():
    check = _cmd("check.md")
    assert "T<n>" in check
    assert "check-spec.py" in check
    assert "--all" in check
    assert "git diff --name-only" not in check
    assert "Hito" not in check


def test_v16_build_cierra_en_ship():
    build = _cmd("build.md")
    assert "Siguiente: /ship" in build or "Siguiente: `/ship`" in build
    assert "/check T<n>" not in build
    assert "/check --all" not in build


def test_v16_spec_y_constitucion():
    if not ES_PLANTILLA:
        return
    assert "V16:" in SPEC
    assert "check-spec.py" in SPEC
    assert "/check` es `python3 .workflow/check-spec.py`" in CLAUDE or "check-spec.py" in CLAUDE


CASOS = [
    test_v14_build_no_invoca_check,
    test_v14_check_es_el_script,
    test_v14_review_no_es_puerta,
    test_v14_constitucion_y_formato,
    test_v16_check_acepta_tarea,
    test_v16_build_cierra_en_ship,
    test_v16_spec_y_constitucion,
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

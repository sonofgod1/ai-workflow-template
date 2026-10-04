#!/usr/bin/env python3
"""Regresión V14 (constructor ≠ auditor) y V16 (check acotado a T<n>).

python3 .workflow/tests/test-spec-auditor.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1].parent
CMD = REPO / ".claude" / "commands"
CLAUDE = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
FORMAT = (REPO / "FORMAT.md").read_text(encoding="utf-8")
SPEC = (REPO / "SPEC.md").read_text(encoding="utf-8")


def _cmd(name):
    return (CMD / name).read_text(encoding="utf-8")


def test_v14_build_no_invoca_check():
    build = _cmd("build.md")
    assert "No invocás `/check`" in build or "No invoques `/check`" in build
    assert "chat nuevo" in build
    assert "verify.sh" in build


def test_v14_check_para_si_el_hilo_construyo():
    check = _cmd("check.md")
    assert "## SEPARACIÓN" in check
    assert "Este hilo construyó. No certifico." in check
    assert "SESGO: mismo hilo que construyó" in check
    assert "chat nuevo" in check


def test_v14_review_para_si_el_hilo_construyo():
    review = _cmd("review.md")
    assert "## SEPARACIÓN" in review
    assert "Este hilo construyó. No certifico." in review
    assert "SESGO: mismo hilo que construyó" in review


def test_v14_constitucion_y_formato():
    assert "El que construye no certifica" in CLAUDE
    assert "otro chat" in CLAUDE.lower() or "otro chat" in CLAUDE
    assert "## CONSTRUCTOR ≠ AUDITOR" in FORMAT
    assert "V14:" in SPEC


def test_v16_check_acepta_tarea():
    check = _cmd("check.md")
    assert "T<n>" in check
    assert "Alcance `T<n>`" in check
    assert "git diff --name-only" in check
    assert "no certifica el resto" in check
    assert "--all" in check and "Hito" in check


def test_v16_build_cierra_con_check_de_tarea():
    build = _cmd("build.md")
    assert "/check T<n>" in build
    assert "/check [--all]" not in build
    assert "/check --all" in build


def test_v16_spec_y_constitucion():
    assert "V16:" in SPEC
    assert "`T<n>`" in SPEC
    assert "/check T<n>" in CLAUDE or "`/check T<n>`" in CLAUDE


CASOS = [
    test_v14_build_no_invoca_check,
    test_v14_check_para_si_el_hilo_construyo,
    test_v14_review_para_si_el_hilo_construyo,
    test_v14_constitucion_y_formato,
    test_v16_check_acepta_tarea,
    test_v16_build_cierra_con_check_de_tarea,
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

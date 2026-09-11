#!/usr/bin/env python3
"""Regresión de check-protected.sh y check-plan-paths.sh.

Lo que este hook pone en riesgo tiene dos caras opuestas y las dos duelen. Dejar
pasar una escritura a un secreto o a un ADR ya escrito es el fallo obvio. El menos
obvio, y el que originó estos tests, es bloquear de más: 'docs/contracts/**' estuvo
como solo-creación hasta el 2026-09-11 (hallazgo I2), lo que dejaba el contrato de
API intocable por cualquier agente apenas se escribía la primera vez.

Cada caso monta un proyecto de verdad en un temporal, con la lista de protegidos
REAL del producto (.claude/protected.txt), no una inventada: lo que se prueba es la
lista que se le entrega a los proyectos.

    python3 .workflow/tests/test-check-protected.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
HOOK = RAIZ / ".claude" / "hooks" / "check-protected.sh"
PLAN_PATHS = RAIZ / ".workflow" / "check-plan-paths.sh"
LISTA = RAIZ / ".claude" / "protected.txt"


def montar(proyecto, archivos=()):
    """Proyecto con la lista de protegidos del producto y los archivos pedidos."""
    (proyecto / ".claude" / "hooks").mkdir(parents=True, exist_ok=True)
    shutil.copy(LISTA, proyecto / ".claude" / "protected.txt")
    shutil.copy(HOOK, proyecto / ".claude" / "hooks" / "check-protected.sh")
    for ruta in archivos:
        p = proyecto / ruta
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("contenido previo\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", "."], cwd=proyecto, check=True)


def escribir(proyecto, ruta, tool="Edit"):
    """Devuelve (permitido, mensaje) para una escritura sobre esa ruta."""
    entrada = json.dumps({
        "tool_name": tool,
        "tool_input": {"file_path": str(proyecto / ruta), "old_string": "contenido previo"},
    })
    r = subprocess.run(
        ["bash", str(proyecto / ".claude" / "hooks" / "check-protected.sh")],
        input=entrada, capture_output=True, text=True, check=False,
        cwd=proyecto, env={"PATH": "/usr/bin:/bin:/usr/local/bin",
                           "CLAUDE_PROJECT_DIR": str(proyecto)},
    )
    return r.returncode == 0, (r.stderr or "").strip()


# ── Casos ────────────────────────────────────────────────────────────────────

def caso_contrato_existente_es_editable():
    """I2: un contrato ya escrito se puede precisar. Es un documento vivo."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        montar(p, ["docs/contracts/api.md"])
        ok, msg = escribir(p, "docs/contracts/api.md")
        assert ok, f"el contrato quedó bloqueado: {msg}"


def caso_contrato_nuevo_se_puede_crear():
    """Quitar la protección no puede romper lo que /contracts ya hacía."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        montar(p)
        ok, msg = escribir(p, "docs/contracts/eventos.md", tool="Write")
        assert ok, f"no se pudo crear un contrato nuevo: {msg}"


def caso_adr_existente_sigue_bloqueado():
    """El arreglo de I2 no puede abrir los ADR: esos sí son inmutables."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        montar(p, ["docs/adr/0001-elegir-postgres.md"])
        ok, msg = escribir(p, "docs/adr/0001-elegir-postgres.md")
        assert not ok, "un ADR ya escrito tiene que seguir bloqueado"
        assert "solo-creación" in msg, msg


def caso_adr_nuevo_se_puede_escribir():
    """La salida de un ADR es escribir otro, y el mensaje del hook lo dice."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        montar(p, ["docs/adr/0001-elegir-postgres.md"])
        ok, _ = escribir(p, "docs/adr/0002-migrar-a-sqlite.md", tool="Write")
        assert ok, "escribir un ADR nuevo es el camino previsto, no puede bloquearse"


def caso_secreto_sigue_bloqueado():
    """Lo que era peligroso antes lo sigue siendo."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        montar(p, [".env"])
        ok, _ = escribir(p, ".env")
        assert not ok, ".env tiene que seguir bloqueado"


def caso_mensaje_no_promete_una_aprobacion_inexistente():
    """I2: el hook decía 'si el usuario lo aprueba' y no había forma de aprobar."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        montar(p, [".env"])
        _, msg = escribir(p, ".env")
        assert "no tiene forma de aprobar" in msg, msg
        assert "pide permiso explícito al usuario" not in msg, (
            "el mensaje vuelve a prometer una aprobación que el hook no implementa: " + msg)


def caso_plan_paths_avisa_antes_de_escribir():
    """I2: las rutas protegidas del plan se declaran antes, no a mitad de camino."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d)
        montar(p, [".env", "docs/contracts/api.md"])
        shutil.copy(PLAN_PATHS, p / "check-plan-paths.sh")
        r = subprocess.run(
            ["bash", str(p / "check-plan-paths.sh"), ".env", "docs/contracts/api.md"],
            capture_output=True, text=True, check=False, cwd=p,
            env={"PATH": "/usr/bin:/bin:/usr/local/bin", "CLAUDE_PROJECT_DIR": str(p)},
        )
        salida = r.stdout + r.stderr
        assert r.returncode == 1, f"tenía que avisar de .env. salida={salida}"
        assert ".env" in salida, salida
        assert "docs/contracts/api.md" not in salida.split("ruta(s)")[0], (
            "el contrato ya no está protegido: no debería aparecer como bloqueado. " + salida)


CASOS = [
    caso_contrato_existente_es_editable,
    caso_contrato_nuevo_se_puede_crear,
    caso_adr_existente_sigue_bloqueado,
    caso_adr_nuevo_se_puede_escribir,
    caso_secreto_sigue_bloqueado,
    caso_mensaje_no_promete_una_aprobacion_inexistente,
    caso_plan_paths_avisa_antes_de_escribir,
]


def main():
    fallos = 0
    for caso in CASOS:
        try:
            caso()
            print(f"  ✓ {caso.__name__} — {(caso.__doc__ or '').strip().splitlines()[0]}")
        except AssertionError as exc:
            fallos += 1
            print(f"  ✗ {caso.__name__}: {exc}")
    print()
    if fallos:
        print(f"❌ {fallos} de {len(CASOS)} casos fallaron.")
        return 1
    print(f"✓ {len(CASOS)} casos en verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

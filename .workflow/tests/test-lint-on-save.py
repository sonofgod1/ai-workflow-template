#!/usr/bin/env python3
"""Regresión de .claude/hooks/lint-on-save.sh.

El hook corría `ruff format` sobre el archivo entero en cada edición. En un archivo
con código preexistente sin formatear eso reescribe líneas que el cambio nunca tocó:
el diff se llena de reformateo ajeno y el commit deja de ser una intención. Pasó en
un proyecto real, sobre media docena de archivos a la vez.

Lo que estos casos fijan es el límite: el hook toca lo que el cambio tocó, y nada
más. El riesgo de la corrección es el contrario — que deje de formatear lo que sí
debería —, así que eso también está aquí.

    python3 .workflow/tests/test-lint-on-save.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent.parent / ".claude" / "hooks" / "lint-on-save.sh"

# Preexistente y feo a propósito: espaciado que `ruff format` reescribiría.
FEO = 'def viejo():\n    return {  "a":1,   "b":2 }\n'
TOCADO_FEO = 'def nuevo():\n    return [  1,2,   3 ]\n'


def sh(repo, cmd):
    return subprocess.run(cmd, cwd=repo, shell=True, capture_output=True, text=True, check=False)


def corre_hook(repo, archivo):
    payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(archivo)}})
    return subprocess.run(["bash", str(HOOK)], input=payload, cwd=repo,
                          capture_output=True, text=True, check=False)


def montar(repo):
    sh(repo, "git init -q . && git config user.email t@t.t && git config user.name t")
    (Path(repo) / "mod.py").write_text(FEO, encoding="utf-8")
    sh(repo, "git add -A && git commit -q -m base")


def caso_no_toca_lo_que_no_cambio():
    """Editar una función deja intacta la de al lado, aunque esté sin formatear."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        archivo = Path(d) / "mod.py"
        archivo.write_text(FEO + "\n" + TOCADO_FEO, encoding="utf-8")
        corre_hook(d, archivo)
        texto = archivo.read_text(encoding="utf-8")
        assert '{  "a":1,   "b":2 }' in texto, \
            "reformateó la función preexistente, que el cambio no tocó:\n" + texto


def caso_si_formatea_lo_que_cambio():
    """Y las líneas que sí se agregaron quedan formateadas."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        archivo = Path(d) / "mod.py"
        archivo.write_text(FEO + "\n" + TOCADO_FEO, encoding="utf-8")
        corre_hook(d, archivo)
        texto = archivo.read_text(encoding="utf-8")
        assert "[  1,2,   3 ]" not in texto, \
            "no formateó la línea nueva, que es para lo que existe el hook:\n" + texto
        assert "[1, 2, 3]" in texto, "el formateo de la línea nueva no es el de ruff:\n" + texto


def caso_archivo_nuevo_se_formatea_entero():
    """Un archivo que git no conoce es todo del cambio: no hay nada ajeno que romper."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        archivo = Path(d) / "nuevo.py"
        archivo.write_text(TOCADO_FEO, encoding="utf-8")
        corre_hook(d, archivo)
        assert "[1, 2, 3]" in archivo.read_text(encoding="utf-8"), \
            "un archivo nuevo sí se formatea completo"


def caso_sin_cambios_no_reescribe():
    """Un archivo idéntico a HEAD no se toca: no hay rango que formatear."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        archivo = Path(d) / "mod.py"
        antes = archivo.read_text(encoding="utf-8")
        corre_hook(d, archivo)
        assert archivo.read_text(encoding="utf-8") == antes, \
            "reescribió un archivo que nadie había cambiado"


def caso_fuera_de_git_no_revienta():
    """Sin repositorio el hook no puede acotar nada, pero tampoco puede fallar."""
    with tempfile.TemporaryDirectory() as d:
        archivo = Path(d) / "suelto.py"
        archivo.write_text(TOCADO_FEO, encoding="utf-8")
        r = corre_hook(d, archivo)
        assert r.returncode == 0, f"el hook falló fuera de un repo: {r.stderr}"


CASOS = [
    caso_no_toca_lo_que_no_cambio,
    caso_si_formatea_lo_que_cambio,
    caso_archivo_nuevo_se_formatea_entero,
    caso_sin_cambios_no_reescribe,
    caso_fuera_de_git_no_revienta,
]


def main():
    if not shutil.which("ruff"):
        print("  ⚠️  ruff no instalado: estos casos no se pueden correr.")
        return 0
    fallos = 0
    for caso in CASOS:
        try:
            caso()
            print(f"  ✓ {caso.__name__} — {(caso.__doc__ or '').strip().splitlines()[0]}")
        except AssertionError as exc:
            fallos += 1
            print(f"  ✗ {caso.__name__}: {str(exc)[:400]}")
    print()
    if fallos:
        print(f"❌ {fallos} de {len(CASOS)} casos fallaron.")
        return 1
    print(f"✓ {len(CASOS)} casos en verde.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

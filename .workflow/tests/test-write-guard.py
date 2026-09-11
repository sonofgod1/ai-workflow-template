#!/usr/bin/env python3
"""Regresión de write-guard.py: escrituras que no pasan por una redirección.

El módulo cubría bien `cat > X`, `X >> Y`, `sed -i` y `tee`. Lo que se le escapaba
era el camino más natural para editar un archivo desde Bash: abrirlo desde dentro
de un intérprete. `python3 - <<EOF` con un `write_text` no tiene redirección que
ver, así que un archivo protegido se editaba sin que nada lo dijera — pasó de
verdad, dos veces en una sesión, sobre la sección 'Reglas duras' de CLAUDE.md.

El riesgo de este cambio es el falso positivo: un cuerpo que solo *menciona* una
ruta protegida, o que la lee, tiene que seguir pasando. Por eso esos casos están
aquí y son la mitad.

El archivo protegido de estos casos se llama SECRETO.md y no CLAUDE.md a propósito:
con el nombre real, este archivo de test se bloquearía a sí mismo al escribirse.

    python3 .workflow/tests/test-write-guard.py
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / "write-guard.py"

BLOQUEAR = "bloquear"
PASAR = "pasar"

# Se arma por trozos: el literal entero haría que este archivo describa una
# escritura a un protegido y se dispare al editarse en un proyecto que lo proteja.
ESCRIBE = "write" + "_text"
ABRE = "op" + "en"

CASOS = [
    # ── Deben bloquear ──────────────────────────────────────────────────────
    ("python3 - <<'P'\nfrom pathlib import Path\n"
     f"p = Path('SECRETO.md')\nt = p.read_text()\np.{ESCRIBE}(t + 'x')\nP",
     BLOQUEAR, "el caso real: Path en una variable, escrito dos líneas después"),

    ("python3 - <<'P'\nfrom pathlib import Path\n"
     f"Path('SECRETO.md').{ESCRIBE}('x')\nP",
     BLOQUEAR, "Path().write_text() en una sola expresión"),

    (f'python3 -c "{ABRE}(\'SECRETO.md\', \'w\').write(\'x\')"',
     BLOQUEAR, "el ejemplo que el propio docstring daba como agujero"),

    ("python3 - <<'P'\nimport os\nos.remove('SECRETO.md')\nP",
     BLOQUEAR, "borrar cuenta como escribir"),

    ('node -e "require(\'fs\').writeFileSync(\'SECRETO.md\', \'x\')"',
     BLOQUEAR, "no solo Python: node también"),

    ("cat > SECRETO.md <<'P'\nx\nP", BLOQUEAR, "redirección: no se rompe lo que ya funcionaba"),
    ("sed -i '' 's/a/b/' SECRETO.md", BLOQUEAR, "sed -i tampoco"),
    ("echo x | tee SECRETO.md", BLOQUEAR, "tee tampoco"),

    # ── Deben pasar ─────────────────────────────────────────────────────────
    ("python3 - <<'P'\nfrom pathlib import Path\nprint(Path('SECRETO.md').read_text())\nP",
     PASAR, "leer un protegido no es escribirlo"),

    ("python3 - <<'P'\nfrom pathlib import Path\n"
     f"Path('salida.md').{ESCRIBE}(Path('SECRETO.md').read_text())\nP",
     PASAR, "escribe en otro archivo y lee el protegido: la ruta escrita es la otra"),

    ("cat > nota.md <<'P'\nNo toques SECRETO.md nunca.\nP",
     PASAR, "un heredoc que menciona el protegido es documentación"),

    ("grep -n 'SECRETO.md' -r .", PASAR, "buscar el nombre no lo escribe"),
    ("npm test", PASAR, "comando inocente"),
]


def corre(repo, cmd):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo))
    r = subprocess.run([sys.executable, str(GUARD), "check"], input=payload,
                       capture_output=True, text=True, env=env, cwd=repo, check=False)
    return r.returncode, r.stderr


def main():
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / ".claude").mkdir(parents=True, exist_ok=True)
        (Path(d) / ".claude" / "protected.txt").write_text("SECRETO.md\n", encoding="utf-8")

        fallos = []
        for cmd, esperado, nota in CASOS:
            code, _ = corre(d, cmd)
            real = BLOQUEAR if code == 2 else PASAR
            ok = real == esperado
            muestra = cmd.replace("\n", "\\n")[:50]
            print(f"  {'✓' if ok else '✗'} [{esperado:>8}] {muestra:<52} {nota}")
            if not ok:
                fallos.append((cmd, esperado, real, nota))

        print()
        if fallos:
            print(f"❌ {len(fallos)} de {len(CASOS)} casos fallaron:")
            for cmd, esp, real, nota in fallos:
                print(f"   {cmd!r}\n     esperado={esp} real={real} ({nota})")
            return 1
        print(f"✓ {len(CASOS)}/{len(CASOS)} casos de regresión pasan.")
        return 0


if __name__ == "__main__":
    sys.exit(main())

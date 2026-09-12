#!/usr/bin/env python3
"""Regresión del reuso de evidencia en verify.sh (hallazgo I4).

Este es el único cambio de la tanda que toca la barrera misma en vez de lo que la
rodea, así que los casos que más importan no son los que ahorran trabajo: son los
que comprueban que NO se reusa cuando la evidencia no describe este árbol. Un
'--reusar' de más da por verificado lo que nadie verificó, que es exactamente el
falso verde de B1 en otra forma.

    python3 .workflow/tests/test-verify-reusar.py
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
VERIFY = RAIZ / "verify.sh"

CONF = 'VERIFY_STEPS=(\n  "test:bash prueba.sh"\n)\n'


def sh(repo, cmd):
    return subprocess.run(cmd, cwd=repo, shell=True, capture_output=True, text=True, check=False)


def montar(repo, prueba="exit 0"):
    p = Path(repo)
    (p / ".workflow").mkdir(parents=True)
    (p / ".workflow" / "verify.sh").write_bytes(VERIFY.read_bytes())
    (p / ".workflow" / "verify.conf").write_text(CONF, encoding="utf-8")
    # Marca de que el paso corrió de verdad: el test lo cuenta.
    (p / "prueba.sh").write_text(f"#!/usr/bin/env bash\necho corrida >> ejecuciones.txt\n{prueba}\n",
                                 encoding="utf-8")
    (p / ".gitignore").write_text(".workflow/.last-verify.json\nejecuciones.txt\n", encoding="utf-8")
    sh(repo, "git init -q . && git config user.email t@t.t && git config user.name t")
    sh(repo, "git add -A && git commit -q -m 'chore: base'")


def verify(repo, *flags):
    return subprocess.run(["bash", ".workflow/verify.sh", *flags], cwd=repo,
                          capture_output=True, text=True, check=False)


def veces_que_corrio(repo):
    f = Path(repo) / "ejecuciones.txt"
    return len(f.read_text(encoding="utf-8").splitlines()) if f.exists() else 0


# ── Lo que importa: cuándo NO se reusa ───────────────────────────────────────

def caso_no_reusa_con_otro_commit():
    """La evidencia de otro commit no describe lo que se va a pushear."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        verify(d)
        Path(d, "otro.txt").write_text("x\n", encoding="utf-8")
        sh(d, "git add -A && git commit -q -m 'chore: otro'")
        r = verify(d, "--reusar")
        assert veces_que_corrio(d) == 2, r.stdout
        assert "otro commit" in r.stdout, r.stdout


def caso_no_reusa_con_arbol_sucio():
    """Si hay cambios sin commitear, la evidencia describe otra cosa."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        verify(d)
        Path(d, "prueba.sh").write_text("#!/usr/bin/env bash\necho corrida >> ejecuciones.txt\n",
                                        encoding="utf-8")
        r = verify(d, "--reusar")
        assert veces_que_corrio(d) == 2, r.stdout
        assert "sin commitear" in r.stdout, r.stdout


def caso_no_reusa_una_corrida_quick():
    """--quick salta los tests y da 'parcial', igual que un parcial legítimo."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        verify(d, "--quick")
        assert veces_que_corrio(d) == 0, "el paso de test no debería correr con --quick"
        r = verify(d, "--reusar")
        assert veces_que_corrio(d) == 1, r.stdout
        assert "--quick" in r.stdout, r.stdout


def caso_no_reusa_si_la_anterior_fallo():
    """Una verificación roja no puede ahorrarle la corrida a la siguiente."""
    with tempfile.TemporaryDirectory() as d:
        montar(d, prueba="exit 1")
        verify(d)
        r = verify(d, "--reusar")
        assert veces_que_corrio(d) == 2, r.stdout
        assert r.returncode != 0, "una evidencia en rojo no puede salir con 0"


def caso_sin_evidencia_corre():
    """Sin registro previo no hay nada que reusar."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        r = verify(d, "--reusar")
        assert veces_que_corrio(d) == 1, r.stdout


# ── Y que efectivamente ahorre cuando corresponde ────────────────────────────

def caso_reusa_mismo_commit_y_arbol_limpio():
    """I4: la puerta corría la suite tres veces sobre el mismo código."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        verify(d)
        r = verify(d, "--reusar")
        assert veces_que_corrio(d) == 1, f"volvió a correr: {r.stdout}"
        assert r.returncode == 0, r.stdout
        assert "reusada" in r.stdout, r.stdout


def caso_reusar_no_reescribe_la_evidencia():
    """Mover el timestamp haría pasar por nueva una verificación vieja."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        verify(d)
        ev = Path(d, ".workflow", ".last-verify.json")
        antes = json.loads(ev.read_text(encoding="utf-8"))
        verify(d, "--reusar")
        despues = json.loads(ev.read_text(encoding="utf-8"))
        assert antes["timestamp"] == despues["timestamp"], (
            "el reuso reescribió la evidencia y ahora miente sobre cuándo se verificó")


def caso_sin_reusar_corre_siempre():
    """El flag es opt-in: sin él, el comportamiento no cambia."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        verify(d)
        verify(d)
        assert veces_que_corrio(d) == 2


CASOS = [
    caso_no_reusa_con_otro_commit,
    caso_no_reusa_con_arbol_sucio,
    caso_no_reusa_una_corrida_quick,
    caso_no_reusa_si_la_anterior_fallo,
    caso_sin_evidencia_corre,
    caso_reusa_mismo_commit_y_arbol_limpio,
    caso_reusar_no_reescribe_la_evidencia,
    caso_sin_reusar_corre_siempre,
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

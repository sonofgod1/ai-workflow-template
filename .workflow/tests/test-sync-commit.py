#!/usr/bin/env python3
"""Regresión del cierre en commit de sync-workflow.sh (hallazgo I1).

Una branch de sync no nace de un plan, así que ningún comando del workflow es dueño
de su commit: /build commitea lo que implementó y /ship exige árbol limpio. El hueco
lo tapaba el humano a mano, que es la acción que el modo PR existe para quitar.

Lo que más importa aquí NO es que commitee: es QUÉ commitea. El comando que este
script sugería antes era 'git add' de las carpetas enteras de SYNC_PATHS, y esas
carpetas también guardan trabajo del proyecto. Un sync que se lleva puesto un cambio
tuyo sin avisar es peor que un sync que no commitea.

El script sale a la red, así que se le pone delante un 'curl' de mentira que sirve un
árbol mínimo. Es el mismo patrón que usan los tests de batch.sh.

    python3 .workflow/tests/test-sync-commit.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
SYNC = RAIZ / "sync-workflow.sh"

# Lo que el "repositorio remoto" ofrece. Dos archivos dentro de SYNC_PATHS.
REMOTO = {
    ".workflow/verify.sh": "#!/usr/bin/env bash\necho verify v2\n",
    ".workflow/phase.sh": "#!/usr/bin/env bash\necho phase v2\n",
}

CURL_FALSO = r"""#!/usr/bin/env bash
# curl de mentira: sirve el árbol y los archivos desde $FAKE_REMOTE.
DEST=""
URL=""
prev=""
for arg in "$@"; do
  [ "$prev" = "-o" ] && DEST="$arg"
  case "$arg" in https://*) URL="$arg" ;; esac
  prev="$arg"
done

if [ -n "$DEST" ]; then
  RUTA="${URL#*/main/}"
  if [ -f "$FAKE_REMOTE/files/$RUTA" ]; then
    cp "$FAKE_REMOTE/files/$RUTA" "$DEST"
    printf '200'
  else
    printf '404'
  fi
  exit 0
fi

cat "$FAKE_REMOTE/tree.json"
printf '\n200\n'
"""


def montar_remoto(base):
    remoto = base / "remoto"
    (remoto / "files").mkdir(parents=True)
    for ruta, contenido in REMOTO.items():
        p = remoto / "files" / ruta
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contenido, encoding="utf-8")
    tree = {"tree": [{"path": r, "type": "blob"} for r in REMOTO]}
    (remoto / "tree.json").write_text(json.dumps(tree), encoding="utf-8")
    return remoto


def montar_proyecto(base, branch="chore/sync"):
    proy = base / "proyecto"
    proy.mkdir()
    subprocess.run(["git", "init", "-q", "."], cwd=proy, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=proy, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=proy, check=True)
    shutil.copy(SYNC, proy / "sync-workflow.sh")
    # Instalación nueva: los archivos del andamiaje todavía no existen, así que el
    # sync los escribe. Si existieran con contenido distinto al del manifest, el
    # script los trataría como personalización tuya y no los pisaría — que es otro
    # camino, correcto, pero no el que estos casos ejercitan.
    (proy / ".workflow").mkdir()
    subprocess.run(["git", "add", "-A"], cwd=proy, check=True)
    subprocess.run(["git", "commit", "-qm", "chore: inicial"], cwd=proy, check=True)
    if branch != "main":
        subprocess.run(["git", "checkout", "-qb", branch], cwd=proy, check=True)
    else:
        subprocess.run(["git", "branch", "-M", "main"], cwd=proy, check=True)
    return proy


def correr(base, proy, *flags):
    bindir = base / "bin"
    bindir.mkdir(exist_ok=True)
    curl = bindir / "curl"
    curl.write_text(CURL_FALSO, encoding="utf-8")
    curl.chmod(0o755)
    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["FAKE_REMOTE"] = str(base / "remoto")
    r = subprocess.run(["bash", "sync-workflow.sh", *flags], cwd=proy,
                       capture_output=True, text=True, check=False, env=env)
    return r.stdout + r.stderr


def commits(proy):
    r = subprocess.run(["git", "log", "--oneline"], cwd=proy,
                       capture_output=True, text=True, check=False)
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def staged_o_sucio(proy, ruta):
    r = subprocess.run(["git", "status", "--porcelain", "--", ruta], cwd=proy,
                       capture_output=True, text=True, check=False)
    return r.stdout.strip()


# ── Casos ────────────────────────────────────────────────────────────────────

def caso_commitea_lo_que_escribio():
    """I1: --commit cierra el sync, sin que el humano tenga que hacerlo a mano."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        montar_remoto(base)
        proy = montar_proyecto(base)
        salida = correr(base, proy, "--commit")
        assert len(commits(proy)) == 2, f"no commiteó. salida={salida}"
        assert "chore: sync workflow" in commits(proy)[0], commits(proy)


def caso_no_arrastra_trabajo_del_proyecto():
    """El riesgo real: 'git add' de carpetas enteras se lleva cambios tuyos."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        montar_remoto(base)
        proy = montar_proyecto(base)
        # Trabajo del proyecto, dentro de una carpeta que el sync toca.
        (proy / ".workflow" / "verify.conf").write_text("VERIFY_STEPS=()\n", encoding="utf-8")
        (proy / ".workflow" / "mio.py").write_text("print('mio')\n", encoding="utf-8")
        correr(base, proy, "--commit")
        for ajeno in (".workflow/verify.conf", ".workflow/mio.py"):
            assert staged_o_sucio(proy, ajeno).startswith("??"), (
                f"{ajeno} entró al commit del sync: sigue sin trackear? "
                f"{staged_o_sucio(proy, ajeno)!r}")


def caso_el_cuerpo_lista_los_archivos():
    """Quien revise el commit tiene que ver qué entró sin abrir el diff."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        montar_remoto(base)
        proy = montar_proyecto(base)
        correr(base, proy, "--commit")
        r = subprocess.run(["git", "log", "-1", "--format=%B"], cwd=proy,
                           capture_output=True, text=True, check=False)
        assert ".workflow/verify.sh" in r.stdout, r.stdout
        assert ".workflow/phase.sh" in r.stdout, r.stdout


def caso_no_commitea_en_main():
    """main solo recibe merges: el sync no puede saltarse eso."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        montar_remoto(base)
        proy = montar_proyecto(base, branch="main")
        salida = correr(base, proy, "--commit")
        assert len(commits(proy)) == 1, f"commiteó en main. salida={salida}"
        assert "no commiteo en main" in salida, salida


def caso_sin_flag_no_commitea():
    """La autorización la da quien ejecuta, no el script por su cuenta."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        montar_remoto(base)
        proy = montar_proyecto(base)
        salida = correr(base, proy)
        assert len(commits(proy)) == 1, f"commiteó sin --commit. salida={salida}"
        assert "--commit" in salida, "no ofrece la salida al usuario"


def caso_sugerencia_nombra_archivos_no_carpetas():
    """El comando que sugería antes ('git add .workflow/') barría de más."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        montar_remoto(base)
        proy = montar_proyecto(base)
        salida = correr(base, proy)
        assert ".workflow/verify.sh" in salida, salida
        # El comando viejo era 'git add ${SYNC_PATHS[*]}', que empieza por las
        # carpetas: git-hooks, .github… Nombrar una sola basta para atraparlo.
        assert "git add git-hooks" not in salida, (
            "vuelve a sugerir añadir carpetas enteras: " + salida)
        assert "git add .github" not in salida, (
            "vuelve a sugerir añadir carpetas enteras: " + salida)


def caso_check_plan_paths_se_reparte():
    """Se abrió al arreglar I2: build.md invoca un script que no se sincronizaba."""
    contenido = SYNC.read_text(encoding="utf-8")
    assert ".workflow/check-plan-paths.sh" in contenido, (
        "check-plan-paths.sh no está en SYNC_PATHS: los proyectos recibirían un "
        "build.md que invoca un script que nunca les llega")


CASOS = [
    caso_commitea_lo_que_escribio,
    caso_no_arrastra_trabajo_del_proyecto,
    caso_el_cuerpo_lista_los_archivos,
    caso_no_commitea_en_main,
    caso_sin_flag_no_commitea,
    caso_sugerencia_nombra_archivos_no_carpetas,
    caso_check_plan_paths_se_reparte,
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

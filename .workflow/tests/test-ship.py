#!/usr/bin/env python3
"""Regresión de ship.sh y pr-body.py.

Dos riesgos, y el orden importa.

El primero es que la puerta deje pasar algo: si ship.sh dice "listo" con el árbol
sucio, sin commits, o con un hallazgo cerrado sin test, el PR abre en rojo y el
trabajo vuelve al humano — que es justo lo que este flujo elimina.

El segundo es que pushee sin autorización. El modo PR contradice la regla dura 3
a propósito, y esa contradicción tiene que ser una decisión explícita del proyecto:
sin delivery.conf, --abrir-pr no puede tocar el remoto. Ese caso va primero.

    python3 .workflow/tests/test-ship.py
"""

import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPTS = ("findings.py", "check-regression.py", "pr-body.py", "ship.sh",
           "verify.sh", "check-migrations.py", "audit-deps.sh")

BUG = "#!/usr/bin/env bash\necho $(( $1 + ${2#-} ))\n"
FIX = "#!/usr/bin/env bash\necho $(( $1 + $2 ))\n"
TEST = '#!/usr/bin/env bash\nR=$(bash src.sh 5 -2)\n[ "$R" = "3" ] || exit 1\n'

PLAN = """# Plan — signo

## Anclaje al norte
El cálculo mal hecho es el que el sistema existe para hacer bien.

## Origen
Hallazgo B1 de docs/reviews/r.md.

## Plan de prueba manual
| # | Acción | Resultado esperado |
|---|--------|--------------------|
| 1 | sumar 5 y -2 | 3 |
"""


def sh(repo, cmd):
    return subprocess.run(cmd, cwd=repo, shell=True, capture_output=True, text=True, check=False)


def ship(repo, *args):
    r = subprocess.run(["bash", ".workflow/ship.sh", *args],
                       cwd=repo, capture_output=True, text=True, check=False)
    return r.stdout + r.stderr, r.returncode


def escribir(repo, ruta, contenido):
    p = Path(repo) / ruta
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(contenido, encoding="utf-8")


def montar(repo, cerrar_bien=True, con_plan=True):
    """Repo con develop, una feature branch, un hallazgo cerrado y su test."""
    for d in (".workflow/tests", "docs/reviews", "docs/plans", "tests"):
        (Path(repo) / d).mkdir(parents=True, exist_ok=True)
    for nombre in SCRIPTS:
        origen = RAIZ / nombre
        if origen.exists():
            (Path(repo) / ".workflow" / nombre).write_bytes(origen.read_bytes())

    sh(repo, "git init -q -b develop . && git config user.email t@t.t && git config user.name t")
    escribir(repo, ".gitignore", ".workflow/.last-verify.json\n.workflow/.phase.json\n"
                                 ".workflow/delivery.conf\n")
    escribir(repo, "docs/reviews/r.md", "# review\n")
    escribir(repo, "src.sh", BUG)
    sh(repo, "git add -A && git commit -q -m 'chore: base'")
    sh(repo, "git checkout -q -b feature/signo")

    if con_plan:
        escribir(repo, "docs/plans/2026-09-09-signo.md", PLAN)
    sh(repo, "python3 .workflow/findings.py add --id B1 --severidad blocker "
             "--titulo 'suma ignora el signo' --origen docs/reviews/r.md")
    escribir(repo, "src.sh", FIX)
    escribir(repo, "tests/test-suma.sh", TEST)
    sh(repo, "git add -A && git commit -q -m 'fix(B1): respetar el signo'")
    sha = sh(repo, "git rev-parse HEAD").stdout.strip()

    if cerrar_bien:
        sh(repo, f"python3 .workflow/findings.py cerrar B1 --commit {sha} "
                 f"--test tests/test-suma.sh --cmd 'bash tests/test-suma.sh' --probar-regresion")
    else:
        sh(repo, f"python3 .workflow/findings.py cerrar B1 --commit {sha} "
                 f"--sin-test --razon 'sin razón de verdad, para el test'")
    sh(repo, "git add -A && git commit -q -m 'docs: marcar B1'")
    return sha


# ── Autorización ─────────────────────────────────────────────────────────────

def caso_sin_delivery_conf_no_pushea():
    """Sin autorización explícita, --abrir-pr no toca el remoto. Regla dura 3."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        salida, code = ship(d, "--abrir-pr")
        assert code != 0, salida
        assert "no autorizó el modo PR" in salida, salida
        assert "git push" not in salida.split("Mientras tanto")[0], \
            "insinuó un push antes de decir que no está autorizado"


def caso_conf_a_medias_no_pushea():
    """MODO_ENTREGA=pr sin AGENTE_PUEDE_PUSHEAR no alcanza: las dos, o ninguna."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        escribir(d, ".workflow/delivery.conf", "MODO_ENTREGA=pr\n")
        salida, code = ship(d, "--abrir-pr")
        assert code != 0 and "no autorizó" in salida, salida


def caso_conf_no_afecta_la_puerta():
    """delivery.conf autoriza el push, no relaja ninguna comprobación."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        escribir(d, ".workflow/delivery.conf",
                 "MODO_ENTREGA=pr\nAGENTE_PUEDE_PUSHEAR=si\n")
        escribir(d, "sucio.txt", "sin commitear\n")
        salida, code = ship(d, "--abrir-pr")
        assert code != 0 and "árbol limpio" in salida, salida


# ── La puerta ────────────────────────────────────────────────────────────────

def caso_arbol_limpio_pasa():
    """El camino feliz: todo commiteado y el hallazgo cerrado con test probado."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        salida, code = ship(d)
        assert code == 0, salida
        assert "ship: listo" in salida, salida


def caso_arbol_sucio_no_pasa():
    """Un PR se abre de lo commiteado: lo que quede fuera no lo revisa nadie."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        escribir(d, "src.sh", FIX + "# tocado sin commitear\n")
        salida, code = ship(d)
        assert code == 1 and "árbol limpio" in salida, salida


def caso_evidencia_generada_no_es_suciedad():
    """.last-verify.json lo escribe el propio andamiaje: no puede trabar la puerta."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        escribir(d, ".gitignore", "")  # sin ignorar nada
        sh(d, "git add -A && git commit -q -m 'chore: gitignore vacío'")
        salida, code = ship(d)
        assert code == 0, f"la evidencia generada trabó la puerta:\n{salida}"


def caso_en_la_base_no_pasa():
    """Un PR sale de una branch de trabajo, no de develop."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        sh(d, "git checkout -q develop")
        salida, code = ship(d)
        assert code == 1 and "no de la base" in salida, salida


def caso_sin_commits_no_pasa():
    """Cero commits sobre la base: el PR estaría vacío."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        sh(d, "git checkout -q develop && git checkout -q -b feature/nada")
        salida, code = ship(d)
        assert code == 1 and "Cero commits" in salida, salida


def caso_hallazgo_sin_test_no_pasa():
    """La puerta corre validate --exigir-test: un cierre sin test no llega al PR."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        # Se rompe el índice a mano: un cerrado al que se le quita el registro del test.
        import json
        p = Path(d) / "docs" / "findings.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        data["hallazgos"][0]["test"] = None
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        sh(d, "git add -A && git commit -q -m 'chore: romper el índice'")
        salida, code = ship(d)
        assert code == 1 and "índice de hallazgos" in salida, salida


def caso_decisiones_desincronizado_no_pasa():
    """decisiones.md editado a mano tampoco llega al PR."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        p = Path(d) / "docs" / "reviews" / "decisiones.md"
        p.write_text(p.read_text(encoding="utf-8") + "\n(a mano)\n", encoding="utf-8")
        sh(d, "git add -A && git commit -q -m 'docs: editar a mano'")
        salida, code = ship(d)
        assert code == 1 and "decisiones.md" in salida, salida


# ── El cuerpo del PR ─────────────────────────────────────────────────────────

def caso_cuerpo_trae_los_artefactos():
    """El cuerpo se arma de lo que ya existe: plan, hallazgo, test, prueba manual."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        cuerpo, code = ship(d, "--cuerpo")
        assert code == 0, cuerpo
        for esperado in ("## Qué cambia", "fix(B1): respetar el signo",
                         "El cálculo mal hecho", "docs/plans/2026-09-09-signo.md",
                         "| B1 |", "probado", "## Qué revisar a mano", "sumar 5 y -2"):
            assert esperado in cuerpo, f"falta {esperado!r} en el cuerpo:\n{cuerpo}"


def caso_cuerpo_en_orden_cronologico():
    """El lector sigue la construcción del cambio, no la deshace desde el final."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        cuerpo, _ = ship(d, "--cuerpo")
        assert cuerpo.index("fix(B1)") < cuerpo.index("docs: marcar B1"), cuerpo


def caso_cuerpo_dice_si_falta_evidencia():
    """Sin .last-verify.json el cuerpo lo dice, no lo omite."""
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        ev = Path(d) / ".workflow" / ".last-verify.json"
        if ev.exists():
            ev.unlink()
        cuerpo, _ = ship(d, "--cuerpo")
        assert "Nadie verificó este cambio localmente" in cuerpo, cuerpo


def caso_cuerpo_traduce_los_estados_de_verify():
    """Los pasos verdes tienen que verse verdes: verify.sh escribe 'pass', no 'ok'.

    El vocabulario de verify.sh y el de pr-body.py se desincronizaron una vez y el
    cuerpo del PR mostró '❓' en los cuatro pasos que habían pasado. Un revisor
    leyendo eso no puede aprobar nada.
    """
    import json
    with tempfile.TemporaryDirectory() as d:
        montar(d)
        ev = Path(d) / ".workflow" / ".last-verify.json"
        ev.write_text(json.dumps({
            "version": 1, "timestamp": "2026-09-09T10:00:00-06:00",
            "git_head": "a" * 40, "git_branch": "feature/signo",
            "working_tree_sucio": False, "resultado": "parcial",
            "pasos": [
                {"paso": "lint", "estado": "pass", "exit_code": 0, "duracion_s": 1},
                {"paso": "test", "estado": "fail", "exit_code": 1, "duracion_s": 2},
                {"paso": "typecheck", "estado": "skipped", "exit_code": 0, "duracion_s": 0},
                {"paso": "raro", "estado": "inventado", "exit_code": 0, "duracion_s": 0},
            ],
        }), encoding="utf-8")
        cuerpo, _ = ship(d, "--cuerpo")
        assert "| `lint` | ✅ |" in cuerpo, cuerpo
        assert "| `test` | ❌ |" in cuerpo, cuerpo
        assert "| `typecheck` | ⚠️ saltado |" in cuerpo, cuerpo
        # Un estado desconocido se muestra tal cual, no como interrogante.
        assert "`inventado`" in cuerpo, cuerpo
        assert "❓" not in cuerpo, cuerpo


def caso_cuerpo_sin_plan_lo_dice():
    """Si no hay plan, el cuerpo lo señala en vez de callarlo."""
    with tempfile.TemporaryDirectory() as d:
        montar(d, con_plan=False)
        cuerpo, _ = ship(d, "--cuerpo")
        assert "Sin plan en `docs/plans/`" in cuerpo, cuerpo


def caso_cuerpo_marca_el_cierre_exento():
    """Un cierre sin test aparece como tal: es donde el revisor tiene que mirar."""
    with tempfile.TemporaryDirectory() as d:
        montar(d, cerrar_bien=False)
        cuerpo, _ = ship(d, "--cuerpo")
        assert "exento" in cuerpo, cuerpo


CASOS = [
    caso_sin_delivery_conf_no_pushea,
    caso_conf_a_medias_no_pushea,
    caso_conf_no_afecta_la_puerta,
    caso_arbol_limpio_pasa,
    caso_arbol_sucio_no_pasa,
    caso_evidencia_generada_no_es_suciedad,
    caso_en_la_base_no_pasa,
    caso_sin_commits_no_pasa,
    caso_hallazgo_sin_test_no_pasa,
    caso_decisiones_desincronizado_no_pasa,
    caso_cuerpo_trae_los_artefactos,
    caso_cuerpo_en_orden_cronologico,
    caso_cuerpo_dice_si_falta_evidencia,
    caso_cuerpo_traduce_los_estados_de_verify,
    caso_cuerpo_sin_plan_lo_dice,
    caso_cuerpo_marca_el_cierre_exento,
]


def main():
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

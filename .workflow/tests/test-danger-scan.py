#!/usr/bin/env python3
"""Regresión de danger-scan.py.

Lo que este cambio pone en riesgo es el falso negativo: aflojar la detección y dejar
pasar algo destructivo. Por eso los casos que deben BLOQUEAR van primero y son la
mayoría. Las cadenas se arman por trozos para que este archivo se pueda editar desde
el propio agente sin dispararse a sí mismo.

    python3 .workflow/tests/test-danger-scan.py
"""

import json
import subprocess
import sys
from pathlib import Path

SCAN = Path(__file__).resolve().parent.parent / "danger-scan.py"

RM = "rm -rf"
DROP = "DROP" + " TABLE"
FORCE = "--" + "force"
DEL = "DELE" + "TE FROM"
UPD = "UPDA" + "TE"

BLOQUEAR = "bloquear"
PASAR = "pasar"

CASOS = [
    # ── Deben bloquear: invocación real ─────────────────────────────────────
    (f"{RM} /", BLOQUEAR, "borrado de raíz"),
    (f"sudo {RM} /", BLOQUEAR, "con sudo delante"),
    (f"FOO=1 {RM} /", BLOQUEAR, "con asignación de entorno delante"),
    (f"{RM} ~", BLOQUEAR, "borrado del home"),
    (f"git push origin main {FORCE}", BLOQUEAR, "push forzado"),
    ("git reset --hard HEAD~3", BLOQUEAR, "reset duro"),
    ("git clean -fd", BLOQUEAR, "clean forzado"),
    (f'psql -c "{DROP} users"', BLOQUEAR, "DDL destructivo vía cliente"),
    (f'sqlite3 app.db "{DROP} users"', BLOQUEAR, "idem sqlite"),
    (f'sh -c "{RM} /"', BLOQUEAR, "dentro de sh -c: por esto no se quitan comillas"),
    (":(){ :|:& };:", BLOQUEAR, "fork bomb"),
    ("dd if=/dev/zero of=/dev/sda", BLOQUEAR, "escritura a dispositivo"),
    ("chmod -R 777 /etc", BLOQUEAR, "permisos totales recursivos"),
    (f"npm test && {RM} /", BLOQUEAR, "segundo segmento de una cadena"),
    (f"echo ok; {RM} /", BLOQUEAR, "tras un punto y coma"),
    (f"echo $({RM} /)", BLOQUEAR, "dentro de una sustitución de comando"),

    # ── Deben bloquear: auditoría, aunque el DELETE esté acotado ────────────
    #
    # El patrón general solo miraba DELETE sin WHERE, así que un borrado de dos
    # filas de un registro de auditoría pasaba limpio. Es el caso peor: acotado
    # es más difícil de notar que vaciado.
    (f'sqlite3 app.db "{DEL} impersonation_log where id in (34,35)"', BLOQUEAR,
     "el caso real: borrado acotado de un registro de impersonaciones"),
    (f'sqlite3 app.db "{UPD} audit_log SET admin_user_id=2 WHERE id=7"', BLOQUEAR,
     "un UPDATE reescribe el historial sin borrar nada"),
    (f"psql -c '{DEL} auditoria WHERE fecha < now()'", BLOQUEAR,
     "auditoría escrita en español"),
    (f'sqlite3 app.db "{DEL} user_history where user_id=4"', BLOQUEAR,
     "history también es historial"),

    # ── Deben pasar: solo mención ───────────────────────────────────────────
    (f'echo "{RM} /"', PASAR, "mención en un echo"),
    (f'echo "{DROP} users"', PASAR, "DDL en un echo, sin cliente"),
    (f'grep -r "{RM} /" .', PASAR, "buscando el texto en el repo"),
    (f'cat > doc.md <<EOF\nNo ejecutes {RM} / nunca.\nEOF', PASAR,
     "heredoc de documentación: el cuerpo es dato"),
    (f'cat > doc.md <<EOF\nEl hook bloquea {DROP} y git push {FORCE}.\nEOF', PASAR,
     "el caso exacto que abrió I3"),
    ("npm test", PASAR, "comando inocente"),
    ("git push origin develop", PASAR, "push normal"),
    ("git push --force-with-lease", PASAR, "force-with-lease no es force"),
    ("rm -rf ./build", PASAR, "borrado acotado a una ruta relativa"),
    ("rm -rf node_modules", PASAR, "borrado acotado sin barra"),
    (f'python3 -c "print(\'{DROP}\')"', PASAR, "DDL impreso, no ejecutado"),

    # ── Deben pasar: ni toda tabla con 'log' es auditoría, ni reponer es borrar ──
    ('sqlite3 app.db "insert into impersonation_log (id) values (34)"', PASAR,
     "reponer una fila borrada no se bloquea: es la salida de quien arregla"),
    (f'sqlite3 app.db "{DEL} catalog where id=1"', PASAR,
     "catalog contiene 'log' y no es un registro de auditoría"),
    (f'sqlite3 app.db "{DEL} blogs where id=1"', PASAR, "blogs tampoco"),
    (f'sqlite3 app.db "{DEL} events where id=1"', PASAR,
     "una tabla de dominio con WHERE sigue pasando"),
    (f'echo "{DEL} impersonation_log where id=34"', PASAR,
     "mención en un echo: sin cliente de base de datos no borra nada"),
]


def corre(cmd):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    r = subprocess.run([sys.executable, str(SCAN)], input=payload,
                       capture_output=True, text=True, check=False)
    return r.returncode, r.stderr


def main():
    fallos = []
    for cmd, esperado, nota in CASOS:
        code, _ = corre(cmd)
        real = BLOQUEAR if code == 2 else PASAR
        ok = real == esperado
        icono = "✓" if ok else "✗"
        muestra = cmd.replace("\n", "\\n")[:52]
        print(f"  {icono} [{esperado:>8}] {muestra:<54} {nota}")
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

#!/usr/bin/env python3
"""Índice de hallazgos del proyecto — fuente de verdad legible por máquina.

Los hallazgos vivían solo en prosa repartida entre docs/reviews/*.md,
decisiones.md y docs/features/*.md, actualizados a mano por el agente. Nadie
podía responder "qué está abierto ahora" sin leer todo, y nada verificaba que
el hash de commit que el agente escribió existiera de verdad. En un proyecto
largo el drift es cuestión de tiempo.

Los reportes en markdown siguen siendo el lugar de la prosa: el síntoma, el por
qué importa, la sugerencia. Este índice guarda solo lo que hay que consultar y
validar: id, severidad, estado, origen y commit.

Uso:
    python3 .workflow/findings.py list [--abiertos] [--severidad blocker]
    python3 .workflow/findings.py add --id B1 --severidad blocker \\
        --titulo "PUT no es atómico" --origen docs/reviews/2026-09-08-api.md \\
        [--archivos backend/api.py:42 ...] [--feature docs/features/x.md]
    python3 .workflow/findings.py cerrar B1 --commit abc1234
    python3 .workflow/findings.py estado B1 --nuevo descartado --nota "..."
    python3 .workflow/findings.py siguiente-id --severidad blocker
    python3 .workflow/findings.py validate [--sin-bloqueantes]
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

STORE = Path("docs/findings.json")

PREFIJOS = {"blocker": "B", "important": "I", "suggestion": "S", "debt": "TD"}
ESTADOS = ("abierto", "en-progreso", "resuelto", "descartado")
ID_RE = re.compile(r"^(TD|[BIS])-?(\d+)(?:\.(\d+))?$")


# ── Almacenamiento ───────────────────────────────────────────────────────────

def cargar():
    if not STORE.exists():
        return {"version": 1, "hallazgos": []}
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
    except ValueError as exc:
        sys.exit(f"❌ {STORE} no es JSON válido: {exc}")
    data.setdefault("hallazgos", [])
    return data


def guardar(data):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def buscar(data, hid):
    for h in data["hallazgos"]:
        if h["id"].upper() == hid.upper():
            return h
    return None


def severidad_de_id(hid):
    m = ID_RE.match(hid.upper())
    if not m:
        return None
    return {"B": "blocker", "I": "important", "S": "suggestion", "TD": "debt"}[m.group(1)]


# ── Comandos ─────────────────────────────────────────────────────────────────

ICONO = {"blocker": "🔴", "important": "🟠", "suggestion": "🟡", "debt": "🔧"}
MARCA = {"abierto": "[ ]", "en-progreso": "[~]", "resuelto": "[x]", "descartado": "[-]"}


def cmd_list(args):
    data = cargar()
    items = data["hallazgos"]
    if args.abiertos:
        items = [h for h in items if h["estado"] in ("abierto", "en-progreso")]
    if args.severidad:
        items = [h for h in items if h["severidad"] == args.severidad]

    if args.json:
        print(json.dumps(items, indent=2, ensure_ascii=False))
        return 0

    if not items:
        print("Sin hallazgos que coincidan.")
        return 0

    orden = {"blocker": 0, "important": 1, "suggestion": 2, "debt": 3}
    for h in sorted(items, key=lambda x: (orden.get(x["severidad"], 9), x["id"])):
        linea = f"{MARCA.get(h['estado'], '[?]')} {ICONO.get(h['severidad'], '')} {h['id']:<6} {h['titulo']}"
        if h.get("commit"):
            linea += f"  ({h['commit'][:7]})"
        print(linea)
        if h.get("archivos"):
            print(f"        {', '.join(h['archivos'])}")

    abiertos = [h for h in items if h["estado"] in ("abierto", "en-progreso")]
    print(f"\n{len(items)} hallazgo(s), {len(abiertos)} sin cerrar.")
    return 0


def cmd_add(args):
    data = cargar()
    hid = args.id.upper()
    if buscar(data, hid):
        sys.exit(f"❌ Ya existe un hallazgo con id {hid}.")
    esperada = severidad_de_id(hid)
    if esperada is None:
        sys.exit(f"❌ Id inválido: {hid}. Formato: B1, I2, S3, TD-004, B1.1")
    if esperada != args.severidad:
        sys.exit(f"❌ El id {hid} corresponde a severidad '{esperada}', no '{args.severidad}'.")

    data["hallazgos"].append({
        "id": hid,
        "severidad": args.severidad,
        "titulo": args.titulo,
        "estado": "abierto",
        "origen": args.origen,
        "archivos": args.archivos or [],
        "feature": args.feature or None,
        "creado": date.today().isoformat(),
        "resuelto": None,
        "commit": None,
        "nota": None,
    })
    guardar(data)
    print(f"✓ {hid} registrado ({args.severidad}) — {args.titulo}")
    return 0


def cmd_cerrar(args):
    data = cargar()
    h = buscar(data, args.id)
    if not h:
        sys.exit(f"❌ No existe el hallazgo {args.id}.")
    sha = resolver_commit(args.commit)
    if sha is None:
        sys.exit(f"❌ '{args.commit}' no es un hash de commit válido de este repositorio.\n"
                 "   Tiene que ser un hash (7-40 caracteres hex), no HEAD ni un nombre de branch:\n"
                 "   esos existen siempre y dejarían pasar un cierre de algo que aún no commiteaste.\n"
                 "   Cierra el hallazgo DESPUÉS de commitear, copiando el hash real.")
    h["estado"] = "resuelto"
    h["commit"] = sha
    h["resuelto"] = date.today().isoformat()
    if args.nota:
        h["nota"] = args.nota
    guardar(data)
    print(f"✓ {h['id']} resuelto en {args.commit[:7]}")
    return 0


def cmd_estado(args):
    data = cargar()
    h = buscar(data, args.id)
    if not h:
        sys.exit(f"❌ No existe el hallazgo {args.id}.")
    if args.nuevo not in ESTADOS:
        sys.exit(f"❌ Estado inválido. Válidos: {', '.join(ESTADOS)}")
    if args.nuevo == "resuelto":
        sys.exit("❌ Para marcar resuelto usa 'cerrar', que exige el hash del commit.")
    h["estado"] = args.nuevo
    if args.nota:
        h["nota"] = args.nota
    guardar(data)
    print(f"✓ {h['id']} → {args.nuevo}")
    return 0


def cmd_siguiente_id(args):
    data = cargar()
    pref = PREFIJOS[args.severidad]
    usados = []
    for h in data["hallazgos"]:
        m = ID_RE.match(h["id"].upper())
        if m and m.group(1) == pref:
            usados.append(int(m.group(2)))
    n = max(usados) + 1 if usados else 1
    print(f"{pref}-{n:03d}" if pref == "TD" else f"{pref}{n}")
    return 0


SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


def commit_existe(sha):
    r = subprocess.run(["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                       capture_output=True, text=True)
    return r.returncode == 0


def resolver_commit(ref):
    """Devuelve el SHA completo, o None si no es un hash de commit válido.

    Rechaza refs simbólicas (HEAD, nombres de branch, tags) a propósito: `HEAD`
    existe siempre y hace pasar la validación aunque el arreglo no esté commiteado
    todavía, que es justo el error que este chequeo tiene que atrapar. El hash se
    copia del commit que ya se hizo.
    """
    if not SHA_RE.match(ref):
        return None
    if not commit_existe(ref):
        return None
    r = subprocess.run(["git", "rev-parse", ref], capture_output=True, text=True)
    return r.stdout.strip() or None


def cmd_validate(args):
    data = cargar()
    problemas = []
    vistos = set()

    for h in data["hallazgos"]:
        hid = h.get("id", "?")
        if hid in vistos:
            problemas.append(f"{hid}: id duplicado")
        vistos.add(hid)

        esperada = severidad_de_id(hid)
        if esperada is None:
            problemas.append(f"{hid}: id con formato inválido")
        elif esperada != h.get("severidad"):
            problemas.append(f"{hid}: severidad '{h.get('severidad')}' no coincide con el prefijo del id")

        if h.get("estado") not in ESTADOS:
            problemas.append(f"{hid}: estado inválido '{h.get('estado')}'")

        if h.get("estado") == "resuelto":
            if not h.get("commit"):
                problemas.append(f"{hid}: marcado resuelto sin commit")
            elif not commit_existe(h["commit"]):
                problemas.append(f"{hid}: el commit {h['commit']} no existe en el repositorio")

        origen = h.get("origen")
        if origen and not Path(origen).exists():
            problemas.append(f"{hid}: el origen '{origen}' no existe")

    if args.sin_bloqueantes:
        abiertos = [h["id"] for h in data["hallazgos"]
                    if h.get("severidad") == "blocker" and h.get("estado") in ("abierto", "en-progreso")]
        if abiertos:
            problemas.append("bloqueantes sin cerrar: " + ", ".join(abiertos))

    if problemas:
        print("❌ Índice de hallazgos inconsistente:")
        for p in problemas:
            print(f"   - {p}")
        return 1

    print(f"✓ Índice de hallazgos consistente ({len(data['hallazgos'])} registrados).")
    return 0


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="listar hallazgos")
    p.add_argument("--abiertos", action="store_true")
    p.add_argument("--severidad", choices=list(PREFIJOS))
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("add", help="registrar un hallazgo")
    p.add_argument("--id", required=True)
    p.add_argument("--severidad", required=True, choices=list(PREFIJOS))
    p.add_argument("--titulo", required=True)
    p.add_argument("--origen", required=True, help="ruta del reporte que lo describe")
    p.add_argument("--archivos", nargs="*")
    p.add_argument("--feature")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("cerrar", help="marcar resuelto (exige commit real)")
    p.add_argument("id")
    p.add_argument("--commit", required=True)
    p.add_argument("--nota")
    p.set_defaults(func=cmd_cerrar)

    p = sub.add_parser("estado", help="cambiar estado")
    p.add_argument("id")
    p.add_argument("--nuevo", required=True, choices=[e for e in ESTADOS if e != "resuelto"])
    p.add_argument("--nota")
    p.set_defaults(func=cmd_estado)

    p = sub.add_parser("siguiente-id", help="siguiente id libre para una severidad")
    p.add_argument("--severidad", required=True, choices=list(PREFIJOS))
    p.set_defaults(func=cmd_siguiente_id)

    p = sub.add_parser("validate", help="verificar consistencia del índice")
    p.add_argument("--sin-bloqueantes", action="store_true",
                   help="fallar si hay bloqueantes sin cerrar (usar en main)")
    p.set_defaults(func=cmd_validate)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

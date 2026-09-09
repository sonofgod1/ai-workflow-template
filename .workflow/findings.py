#!/usr/bin/env python3
"""Índice de hallazgos del proyecto — fuente de verdad legible por máquina.

Los hallazgos vivían solo en prosa repartida entre docs/reviews/*.md,
decisiones.md y docs/features/*.md, actualizados a mano por el agente. Nadie
podía responder "qué está abierto ahora" sin leer todo, y nada verificaba que
el hash de commit que el agente escribió existiera de verdad. En un proyecto
largo el drift es cuestión de tiempo.

Los reportes en markdown siguen siendo el lugar de la prosa: el síntoma, el por
qué importa, la sugerencia. Este índice guarda solo lo que hay que consultar y
validar: id, severidad, estado, origen, commit y el test que lo cubre.

Cerrar exige nombrar un test, o registrar por qué no lo hay. Un hallazgo cerrado
sin test deja al humano como único arnés de pruebas: la próxima vez que alguien
rompa eso, nadie se enterará hasta que un humano lo vuelva a probar a mano.

`docs/reviews/decisiones.md` se genera desde aquí en cada cambio, y no se edita a
mano. Mantenerlo sincronizado era un paso manual del ciclo, y un paso manual que
duplica un dato es una fuente de drift con fecha de caducidad.

Uso:
    python3 .workflow/findings.py list [--abiertos] [--severidad blocker]
    python3 .workflow/findings.py add --id B1 --severidad blocker \\
        --titulo "PUT no es atómico" --origen docs/reviews/2026-09-08-api.md \\
        [--archivos backend/api.py:42 ...] [--feature docs/features/x.md]
    python3 .workflow/findings.py cerrar B1 --commit abc1234 \\
        --test tests/test_api.py::test_put_atomico [--probar-regresion]
    python3 .workflow/findings.py cerrar B1 --commit abc1234 \\
        --sin-test --razon "cambio de copy, no hay comportamiento que ejercitar"
    python3 .workflow/findings.py test-exento B1 --razon "..."
    python3 .workflow/findings.py estado B1 --nuevo descartado --nota "..."
    python3 .workflow/findings.py siguiente-id --severidad blocker
    python3 .workflow/findings.py decisiones [--check]
    python3 .workflow/findings.py validate [--sin-bloqueantes] [--exigir-test]
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

STORE = Path("docs/findings.json")
DECISIONES = Path("docs/reviews/decisiones.md")

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
    # decisiones.md se regenera aquí y no en cada comando: así no existe el estado
    # en el que el índice ya cambió y el markdown todavía no. Antes eran dos pasos
    # manuales del ciclo, y el segundo se olvidaba.
    escribir_decisiones(data)


def escribir_decisiones(data):
    DECISIONES.parent.mkdir(parents=True, exist_ok=True)
    DECISIONES.write_text(render_decisiones(data), encoding="utf-8")


def clave_orden(h):
    """Orden estable: por severidad, y dentro de ella por número, no por texto.

    Ordenar los ids como cadenas pone B10 antes de B2 y hace que el archivo
    generado cambie de forma impredecible. Con --check en CI eso sería un fallo
    intermitente.
    """
    orden = {"blocker": 0, "important": 1, "suggestion": 2, "debt": 3}
    m = ID_RE.match(h.get("id", "").upper())
    num = int(m.group(2)) if m else 0
    sub = int(m.group(3)) if m and m.group(3) else 0
    return (orden.get(h.get("severidad"), 9), num, sub)


CABECERA = """<!-- GENERADO por .workflow/findings.py — NO EDITAR A MANO.
     Cualquier cambio aquí se pierde en el próximo add/cerrar/estado.

     La prosa vive en dos sitios, no en este archivo:
       - el reporte de review (docs/reviews/*.md): síntoma, por qué importa, sugerencia
       - la nota del hallazgo: python3 .workflow/findings.py estado I2 \\
             --nuevo descartado --nota "el caso no puede ocurrir porque ..."

     Regenerar a mano: python3 .workflow/findings.py decisiones
     Comprobar que está al día (CI): python3 .workflow/findings.py decisiones --check
-->

# Decisiones de triaje

*Estado de cada hallazgo, generado desde `docs/findings.json`.*
"""


def _tabla(filas, columnas):
    out = ["| " + " | ".join(columnas) + " |",
           "|" + "|".join("---" for _ in columnas) + "|"]
    out += ["| " + " | ".join(f) + " |" for f in filas]
    return out


def _celda(txt):
    """Neutraliza lo que rompería la tabla: el pipe y los saltos de línea."""
    if not txt:
        return "—"
    return str(txt).replace("|", "\\|").replace("\n", " ").strip() or "—"


def _archivos(h):
    return ", ".join(f"`{a}`" for a in h.get("archivos") or []) or "—"


def _origen(h):
    o = h.get("origen")
    return f"[reporte]({o})" if o else "—"


def _test(h):
    t = h.get("test") or {}
    estado = t.get("estado")
    if estado == "probado":
        return "✅ probado — " + ", ".join(f"`{r}`" for r in t.get("rutas") or [])
    if estado == "declarado":
        return "⚠️ declarado — " + ", ".join(f"`{r}`" for r in t.get("rutas") or [])
    if estado == "exento":
        return f"➖ exento: {_celda(t.get('razon'))}"
    return "❌ sin registrar"


SECCIONES = [
    ("🔴 Arreglar ahora — bloqueantes sin cerrar", "blocker", ("abierto", "en-progreso")),
    ("🟠 Importantes sin cerrar", "important", ("abierto", "en-progreso")),
    ("🟡 Sugerencias sin cerrar", "suggestion", ("abierto", "en-progreso")),
    ("🔧 Deuda técnica sin cerrar", "debt", ("abierto", "en-progreso")),
]


def render_decisiones(data):
    """Construye decisiones.md desde el índice. Determinista: mismo índice, mismo texto.

    No lleva fecha de generación a propósito. Una fecha de "hoy" haría que --check
    fallara al día siguiente sin que nadie hubiera cambiado nada.
    """
    hallazgos = sorted(data.get("hallazgos", []), key=clave_orden)
    lineas = [CABECERA]

    abiertos = [h for h in hallazgos if h.get("estado") in ("abierto", "en-progreso")]
    resueltos = [h for h in hallazgos if h.get("estado") == "resuelto"]
    descartados = [h for h in hallazgos if h.get("estado") == "descartado"]
    lineas.append(f"**{len(hallazgos)} hallazgo(s):** {len(abiertos)} sin cerrar, "
                  f"{len(resueltos)} resuelto(s), {len(descartados)} descartado(s).\n")

    if not hallazgos:
        lineas.append("Sin hallazgos registrados todavía.\n")
        return "\n".join(lineas)

    for titulo, sev, estados in SECCIONES:
        items = [h for h in hallazgos if h.get("severidad") == sev and h.get("estado") in estados]
        if not items:
            continue
        lineas.append(f"\n## {titulo}\n")
        lineas += _tabla(
            [(h["id"], _celda(h.get("titulo")), _archivos(h), _celda(h.get("estado")),
              _origen(h), _celda(h.get("nota"))) for h in items],
            ("ID", "Título", "Archivo(s)", "Estado", "Origen", "Nota"))

    if resueltos:
        lineas.append("\n## ✅ Resueltos\n")
        lineas += _tabla(
            [(h["id"], _celda(h.get("titulo")), f"`{h['commit'][:7]}`" if h.get("commit") else "—",
              _test(h), _celda(h.get("resuelto"))) for h in resueltos],
            ("ID", "Título", "Commit", "Test", "Fecha"))

    if descartados:
        lineas.append("\n## ⚪ Descartados\n")
        lineas += _tabla(
            [(h["id"], _celda(h.get("titulo")), _celda(h.get("nota"))) for h in descartados],
            ("ID", "Título", "Razón"))

    return "\n".join(lineas) + "\n"


def cmd_decisiones(args):
    data = cargar()
    esperado = render_decisiones(data)
    if args.check:
        actual = DECISIONES.read_text(encoding="utf-8") if DECISIONES.exists() else None
        if actual == esperado:
            print(f"✓ {DECISIONES} está al día.")
            return 0
        falta = "no existe" if actual is None else "está desactualizado"
        print(f"❌ {DECISIONES} {falta} respecto a {STORE}.")
        print("   Es un archivo generado: no se edita a mano, se regenera.")
        print("   Regenera con: python3 .workflow/findings.py decisiones")
        return 1
    escribir_decisiones(data)
    print(f"✓ {DECISIONES} regenerado desde {STORE}.")
    return 0


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
        "test": None,
    })
    guardar(data)
    print(f"✓ {hid} registrado ({args.severidad}) — {args.titulo}")
    return 0


FALTA_TEST = """❌ Cerrar un hallazgo exige el test que lo cubre.

   Un arreglo sin test deja al humano como único arnés de pruebas: la próxima vez
   que alguien rompa esto, nadie se entera hasta que se vuelva a probar a mano.

   Con test:   --test tests/test_api.py::test_put_atomico
   Y para saber si el test sirve de verdad, agrega --probar-regresion: monta el
   árbol sin el arreglo y comprueba que ahí el test falla.

   Sin test:   --sin-test --razon "..."
   Es válido (un cambio de copy, un README, un ajuste de CI no tienen comportamiento
   que ejercitar), pero queda registrado con su razón. Una exención sin razón se
   vuelve permanente y nadie recuerda por qué está ahí."""


def verificar_test_en_commit(sha, specs):
    """Comprueba que cada test exista EN el commit del arreglo, no solo en el disco."""
    rutas = [spec.split("::", 1)[0] for spec in specs]
    for ruta in rutas:
        r = subprocess.run(["git", "cat-file", "-e", f"{sha}:{ruta}"],
                           capture_output=True, text=True, check=False)
        if r.returncode != 0:
            sys.exit(f"❌ '{ruta}' no existe en el commit {sha[:7]}.\n"
                     "   El test tiene que estar commiteado junto al arreglo, no solo en tu disco.")

    tocados = subprocess.run(["git", "show", "--name-only", "--format=", sha],
                             capture_output=True, text=True, check=False).stdout.split()
    sin_tocar = [r for r in rutas if r not in tocados]
    if sin_tocar:
        # No es un fallo: en test-first el test ya venía de un commit anterior.
        print(f"⚠️  {', '.join(sin_tocar)} no cambió en {sha[:7]}. Si el test ya existía y")
        print("   pasaba antes del arreglo, no cubre este hallazgo. Verifícalo con --probar-regresion.")
    return rutas


def probar_regresion(sha, specs, cmd):
    """Delega en check-regression.py. Devuelve (resultado, razón)."""
    script = Path(__file__).resolve().parent / "check-regression.py"
    if not script.exists():
        return "no-verificada", f"falta {script}"
    argv = [sys.executable, str(script), "--commit", sha, "--json", "--test", *specs]
    if cmd:
        argv += ["--cmd", cmd]
    r = subprocess.run(argv, capture_output=True, text=True, check=False)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return "no-verificada", f"check-regression.py no devolvió JSON: {r.stderr.strip()[:200]}"
    return out.get("resultado", "no-verificada"), out.get("razon", "")


def cmd_cerrar(args):
    data = cargar()
    h = buscar(data, args.id)
    if not h:
        sys.exit(f"❌ No existe el hallazgo {args.id}.")

    if args.test and args.sin_test:
        sys.exit("❌ --test y --sin-test se excluyen: o hay test o hay razón de por qué no.")
    if not args.test and not args.sin_test:
        sys.exit(FALTA_TEST)
    if args.sin_test and not args.razon:
        sys.exit("❌ --sin-test exige --razon. Una exención sin razón se vuelve permanente\n"
                 "   y nadie recuerda por qué está ahí.")

    sha = resolver_commit(args.commit)
    if sha is None:
        sys.exit(f"❌ '{args.commit}' no es un hash de commit válido de este repositorio.\n"
                 "   Tiene que ser un hash (7-40 caracteres hex), no HEAD ni un nombre de branch:\n"
                 "   esos existen siempre y dejarían pasar un cierre de algo que aún no commiteaste.\n"
                 "   Cierra el hallazgo DESPUÉS de commitear, copiando el hash real.")

    if args.sin_test:
        test = {"estado": "exento", "rutas": [], "razon": args.razon,
                "regresion": None, "verificado": date.today().isoformat()}
    else:
        verificar_test_en_commit(sha, args.test)
        test = {"estado": "declarado", "rutas": list(args.test), "razon": None,
                "regresion": None, "verificado": date.today().isoformat()}

        if args.probar_regresion:
            resultado, razon = probar_regresion(sha, args.test, args.cmd)
            test["regresion"] = resultado
            if resultado == "no-prueba-nada":
                # Aquí es donde este chequeo gana su sitio: el test existe, la suite
                # está verde, y no habría atrapado el bug. Cerrar sería mentir.
                sys.exit(f"❌ El test pasa SIN el arreglo: {razon}.\n"
                         "   No demuestra nada. Tiene que ejercitar el camino que fallaba,\n"
                         "   con los datos que lo hacían fallar. El hallazgo sigue abierto.")
            if resultado == "confirmada":
                test["estado"] = "probado"
                print(f"✓ Regresión confirmada: {razon}.")
            else:
                print(f"⚠️  Regresión sin verificar ({resultado}): {razon}.")
                print("   El test queda 'declarado', no 'probado'. Esto NO es verde.")

    h["estado"] = "resuelto"
    h["commit"] = sha
    h["resuelto"] = date.today().isoformat()
    h["test"] = test
    if args.nota:
        h["nota"] = args.nota
    guardar(data)
    etiqueta = {"probado": "con test probado", "declarado": "con test declarado",
                "exento": "exento de test"}[test["estado"]]
    print(f"✓ {h['id']} resuelto en {args.commit[:7]} — {etiqueta}")
    return 0


def cmd_test_exento(args):
    """Registra la exención en un hallazgo ya cerrado.

    Existe para dos casos reales: los hallazgos que se cerraron antes de que esta
    regla existiera, y el descubrimiento tardío de que un arreglo no tiene
    comportamiento que ejercitar.
    """
    data = cargar()
    h = buscar(data, args.id)
    if not h:
        sys.exit(f"❌ No existe el hallazgo {args.id}.")
    h["test"] = {"estado": "exento", "rutas": [], "razon": args.razon,
                 "regresion": None, "verificado": date.today().isoformat()}
    guardar(data)
    print(f"✓ {h['id']} exento de test — {args.razon}")
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
                       capture_output=True, text=True, check=False)
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
    r = subprocess.run(["git", "rev-parse", ref], capture_output=True, text=True, check=False)
    return r.stdout.strip() or None


def revisar_test(h, hid):
    """Comprueba que un hallazgo cerrado tenga test, o una exención con razón.

    Verifica además que el test siga existiendo en el commit que lo cerró. Un test
    borrado después deja el hallazgo sin cobertura y el índice diciendo que sí la
    tiene: es exactamente el drift que este índice existe para no permitir.
    """
    test = h.get("test")
    if not test:
        return [f"{hid}: cerrado sin test ni exención registrada "
                f"(usa 'test-exento {hid} --razon ...' si no hay comportamiento que ejercitar)"]

    estado = test.get("estado")
    if estado == "exento":
        if not test.get("razon"):
            return [f"{hid}: exento de test sin razón registrada"]
        return []
    if estado not in ("declarado", "probado"):
        return [f"{hid}: estado de test inválido '{estado}'"]
    if not test.get("rutas"):
        return [f"{hid}: test '{estado}' sin rutas"]

    problemas = []
    for spec in test["rutas"]:
        ruta = spec.split("::", 1)[0]
        r = subprocess.run(["git", "cat-file", "-e", f"{h['commit']}:{ruta}"],
                           capture_output=True, text=True, check=False)
        if r.returncode != 0:
            problemas.append(f"{hid}: el test '{ruta}' no existe en {h['commit'][:7]}")
        elif not Path(ruta).exists():
            problemas.append(f"{hid}: el test '{ruta}' existía al cerrarlo y ya no está en el árbol")
    return problemas


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
            if args.exigir_test:
                problemas.extend(revisar_test(h, hid))

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
    if args.exigir_test:
        cerrados = [h for h in data["hallazgos"] if h.get("estado") == "resuelto"]
        probados = [h for h in cerrados if (h.get("test") or {}).get("estado") == "probado"]
        exentos = [h for h in cerrados if (h.get("test") or {}).get("estado") == "exento"]
        declarados = len(cerrados) - len(probados) - len(exentos)
        print(f"  Cerrados: {len(cerrados)} — {len(probados)} con regresión probada, "
              f"{declarados} con test declarado, {len(exentos)} exentos.")
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

    p = sub.add_parser("cerrar", help="marcar resuelto (exige commit real y test)")
    p.add_argument("id")
    p.add_argument("--commit", required=True)
    p.add_argument("--test", nargs="+", metavar="RUTA[::NOMBRE]",
                   help="test que falla sin este arreglo")
    p.add_argument("--probar-regresion", action="store_true",
                   help="comprobar que el test falla en el árbol sin el arreglo")
    p.add_argument("--cmd", help="comando para correr el test (si el automático no sirve)")
    p.add_argument("--sin-test", action="store_true",
                   help="cerrar sin test; exige --razon y queda registrado")
    p.add_argument("--razon", help="por qué no hay test (obligatorio con --sin-test)")
    p.add_argument("--nota")
    p.set_defaults(func=cmd_cerrar)

    p = sub.add_parser("test-exento", help="registrar exención de test en un hallazgo ya cerrado")
    p.add_argument("id")
    p.add_argument("--razon", required=True)
    p.set_defaults(func=cmd_test_exento)

    p = sub.add_parser("estado", help="cambiar estado")
    p.add_argument("id")
    p.add_argument("--nuevo", required=True, choices=[e for e in ESTADOS if e != "resuelto"])
    p.add_argument("--nota")
    p.set_defaults(func=cmd_estado)

    p = sub.add_parser("siguiente-id", help="siguiente id libre para una severidad")
    p.add_argument("--severidad", required=True, choices=list(PREFIJOS))
    p.set_defaults(func=cmd_siguiente_id)

    p = sub.add_parser("decisiones", help="regenerar docs/reviews/decisiones.md")
    p.add_argument("--check", action="store_true",
                   help="no escribir; fallar si el archivo no coincide con el índice (CI)")
    p.set_defaults(func=cmd_decisiones)

    p = sub.add_parser("validate", help="verificar consistencia del índice")
    p.add_argument("--sin-bloqueantes", action="store_true",
                   help="fallar si hay bloqueantes sin cerrar (usar en main)")
    p.add_argument("--exigir-test", action="store_true",
                   help="fallar si algún hallazgo cerrado no tiene test ni exención")
    p.set_defaults(func=cmd_validate)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

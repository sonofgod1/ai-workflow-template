#!/usr/bin/env python3
"""Arma el cuerpo del PR desde lo que el proyecto ya produjo.

El humano no debería tener que reconstruir el contexto de un cambio leyendo
commits: el plan, los hallazgos cerrados, la evidencia de verificación y la prueba
de regresión ya existen como artefactos. Esto los junta en una página.

Es la pieza que hace que "revisar el PR" pueda sustituir a aprobar el plan, correr
la prueba manual, commitear y mergear uno por uno. Si el cuerpo del PR no dice qué
cambia, por qué, con qué evidencia y qué falta revisar a mano, el humano vuelve a
ser el integrador.

Uso:
    python3 .workflow/pr-body.py [--base develop] [--salida /tmp/cuerpo.md]
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

FINDINGS = Path("docs/findings.json")
VERIFY = Path(".workflow/.last-verify.json")
PLANES = Path("docs/plans")


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    return r.stdout.strip() if r.returncode == 0 else ""


def cargar_json(p):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None


def commits_del_rango(base, cabeza):
    # --reverse: en orden cronológico. El lector del PR sigue la construcción del
    # cambio, no la deshace desde el final.
    crudo = git("log", "--reverse", "--format=%H%x1f%s", f"{base}..{cabeza}")
    salida = []
    for linea in crudo.splitlines():
        if "\x1f" in linea:
            sha, asunto = linea.split("\x1f", 1)
            salida.append((sha, asunto))
    return salida


ID_EN_ASUNTO = re.compile(r"^[a-z]+\(([A-Za-z]{1,3}-?\d+(?:\.\d+)?)\)")


def ids_del_rango(asuntos, cerrados):
    """IDs de hallazgo que este PR dice tocar: del scope de los commits y de lo cerrado."""
    ids = {h.get("id") for h in cerrados if h.get("id")}
    for a in asuntos:
        m = ID_EN_ASUNTO.match(a)
        if m:
            ids.add(m.group(1).upper())
    return {i for i in ids if i}


def _palabras(s):
    # Se descartan las de 1-2 letras y los números: un "2026" o un "de" compartido
    # no dice nada, y con el umbral bajo cualquier plan empata con cualquier branch.
    return {w for w in re.split(r"[^A-Za-z0-9]+", s.lower()) if len(w) > 2 and not w.isdigit()}


def plan_probable(branch, base, cabeza, cerrados, asuntos):
    """Busca el plan de este PR. Devuelve (plan, cómo se encontró, candidatos).

    Tres señales, de la más fiable a la más débil:

    1. Un plan que esta branch agregó o tocó es el plan de esta branch. No depende
       de ningún nombre, así que es la única que no se rompe cuando el humano nombra
       la branch y el archivo del plan por separado — que es lo normal.
    2. El ID del hallazgo, que ya está en el scope del commit (`fix(B2):`) y dentro
       del plan. Cubre el caso de un plan commiteado en la base antes de ramificar.
    3. El parecido de nombres. Era lo único que había, y falla en cuanto los nombres
       no coinciden: `fix/naive-datetimes` contra `2026-09-09-b2-datetimes-aware.md`
       no matcheaba, y el cuerpo degradaba a "Sin plan" sin decir que había buscado.

    Varias coincidencias se devuelven como ambigüedad (plan None, candidatos con las
    que empataron): elegir una al azar pondría el "por qué" de otro cambio en este PR,
    que es peor que no poner ninguno.
    """
    if not PLANES.is_dir():
        return None, None, []
    candidatos = sorted(PLANES.glob("*.md"), reverse=True)
    if not candidatos:
        return None, None, []

    tocados = [Path(a) for a in git("diff", "--name-only", f"{base}..{cabeza}").splitlines()
               if a.startswith(f"{PLANES}/") and a.endswith(".md")]
    tocados = [q for q in tocados if q.exists()]
    if len(tocados) == 1:
        return tocados[0], "lo agregó o lo tocó esta branch", candidatos
    if len(tocados) > 1:
        return None, None, tocados

    ids = ids_del_rango(asuntos, cerrados)
    if ids:
        por_id = [q for q in candidatos
                  if any(re.search(rf"\b{re.escape(i)}\b",
                                   q.read_text(encoding="utf-8", errors="replace"))
                         for i in ids)]
        if len(por_id) == 1:
            return por_id[0], f"nombra {', '.join(sorted(ids))}", candidatos
        if len(por_id) > 1:
            return None, None, por_id

    slug = re.sub(r"^(feature|fix|hotfix|chore)/", "", branch)
    exactos = [q for q in candidatos if slug and slug in q.name]
    if exactos:
        return exactos[0], "el nombre de la branch está en el del plan", candidatos

    palabras = _palabras(slug)
    if palabras:
        puntuados = sorted(((len(palabras & _palabras(q.stem)), q) for q in candidatos),
                           key=lambda par: (-par[0], par[1].name))
        mejor, q = puntuados[0]
        if mejor and sum(1 for n, _ in puntuados if n == mejor) == 1:
            comunes = ", ".join(sorted(palabras & _palabras(q.stem)))
            return q, f"comparte «{comunes}» con el nombre de la branch", candidatos

    return None, None, candidatos


def seccion_del_plan(plan, titulo):
    """Extrae una sección '## titulo' del plan, para no duplicar su contenido a mano."""
    if not plan or not plan.exists():
        return None
    texto = plan.read_text(encoding="utf-8")
    m = re.search(rf"^##\s+{re.escape(titulo)}\s*$(.*?)(?=^##\s|\Z)",
                  texto, re.MULTILINE | re.DOTALL)
    return m.group(1).strip() if m else None


def hallazgos_cerrados(shas):
    data = cargar_json(FINDINGS)
    if not data:
        return []
    cortos = {s[:7] for s in shas}
    salida = []
    for h in data.get("hallazgos", []):
        c = h.get("commit") or ""
        if h.get("estado") == "resuelto" and (c in shas or c[:7] in cortos):
            salida.append(h)
    return salida


def texto_test(h):
    t = h.get("test") or {}
    estado = t.get("estado")
    rutas = ", ".join(f"`{r}`" for r in t.get("rutas") or [])
    if estado == "probado":
        return f"✅ probado — {rutas}", "falla sin el arreglo (comprobado)"
    if estado == "declarado":
        return f"⚠️ declarado — {rutas}", "sin comprobar contra el árbol sin el arreglo"
    if estado == "exento":
        return "➖ exento", t.get("razon") or "sin razón registrada"
    return "❌ sin registrar", "—"


def bloque_verificacion():
    data = cargar_json(VERIFY)
    if not data:
        return ("No hay `.workflow/.last-verify.json`. **Nadie verificó este cambio "
                "localmente**; lo que diga CI es todo lo que hay.")
    resultado = data.get("resultado", "?")
    pasos = data.get("pasos", [])
    icono = {"ok": "✅", "parcial": "⚠️", "falla": "❌"}.get(resultado, "❓")
    lineas = [f"{icono} **{resultado}** — commit `{(data.get('git_head') or '')[:7]}`, "
              f"branch `{data.get('git_branch', '?')}`, {data.get('timestamp', '?')}"]
    if data.get("working_tree_sucio"):
        lineas.append("")
        lineas.append("El árbol estaba sucio al verificar: la evidencia no corresponde "
                      "exactamente a lo commiteado.")
    if pasos:
        lineas.append("")
        lineas.append("| Paso | Estado |")
        lineas.append("|------|--------|")
        # verify.sh escribe pass/fail/skipped. Se aceptan también los sinónimos por
        # si el vocabulario cambia, y un estado desconocido se muestra tal cual: un
        # "❓" oculta el dato en vez de reportarlo, que es lo contrario de lo que
        # este cuerpo tiene que hacer.
        marcas = {"pass": "✅", "ok": "✅",
                  "fail": "❌", "failed": "❌",
                  "skipped": "⚠️ saltado", "skip": "⚠️ saltado"}
        for p in pasos:
            estado = str(p.get("estado", ""))
            marca = marcas.get(estado, f"`{estado or 'sin estado'}`")
            lineas.append(f"| `{p.get('paso')}` | {marca} |")
    if resultado == "parcial":
        lineas.append("")
        lineas.append("**`parcial` no es verde:** hay pasos que no corrió nadie localmente. "
                      "CI los corre en un entorno limpio; si allí también quedan saltados, "
                      "este cambio se mergea sin esa cobertura.")
    return "\n".join(lineas)


def migraciones_tocadas(base, cabeza):
    archivos = git("diff", "--name-only", f"{base}..{cabeza}").splitlines()
    return [a for a in archivos
            if re.search(r"(migrations?|alembic|schema)/", a) and a.endswith((".py", ".sql", ".js", ".ts"))]


# Rutas que son andamiaje del workflow, no código del proyecto. Una branch que solo
# las toca viene de sync-workflow.sh, no de un plan — y exigirle uno, o proponerle
# planes de otros cambios como "candidatos", es ruido que invita a contestar mal.
ANDAMIAJE = (
    ".workflow/", ".claude/", ".cursor/", "git-hooks/", ".github/",
    "sync-workflow.sh", "generate-cursor-rules.sh",
)


def solo_andamiaje(base, cabeza):
    """True si la branch no toca nada del proyecto. Falso si no tocó nada en absoluto.

    Existe por el hallazgo S2: para una branch de sync no hay plan POR DISEÑO, y
    tratarlo como un hueco manda al revisor a buscar algo que no existe.
    """
    archivos = [a for a in git("diff", "--name-only", f"{base}..{cabeza}").splitlines() if a]
    if not archivos:
        return False
    return all(a.startswith(ANDAMIAJE) for a in archivos)


def construir(base, cabeza, branch):
    rango = commits_del_rango(base, cabeza)
    shas = [s for s, _ in rango]
    asuntos = [a for _, a in rango]
    cerrados = hallazgos_cerrados(shas)
    plan, como, candidatos = plan_probable(branch, base, cabeza, cerrados, asuntos)

    out = []

    out.append("## Qué cambia\n")
    if asuntos:
        out += [f"- {a}" for a in asuntos]
    else:
        out.append("_Sin commits sobre la base. Este PR está vacío._")
    out.append("")

    out.append("## Por qué\n")
    anclaje = seccion_del_plan(plan, "Anclaje al norte")
    origen = seccion_del_plan(plan, "Origen")
    if anclaje:
        out.append(anclaje)
        out.append("")
    if origen:
        out.append(origen)
        out.append("")
    if plan:
        out.append(f"Plan completo: [`{plan}`]({plan}) — encontrado porque {como}.")
    elif not anclaje and not origen:
        # No encontrar el plan y callarlo es el peor fallo posible de este cuerpo: se
        # pierde el "por qué" justo donde el revisor viene a buscarlo, y nada avisa.
        # Si hay planes en el repo, se listan: que el revisor vea qué se descartó.
        #
        # Salvo cuando la branch es solo andamiaje: ahí no hay plan porque no debe
        # haberlo, y el aviso sería un falso positivo que además ofrece planes de
        # otros cambios como candidatos.
        if solo_andamiaje(base, cabeza):
            out.append("**Sync del andamiaje del workflow — sin plan, y es lo correcto.** "
                       "Esta branch no toca código del proyecto: trae los archivos del "
                       "workflow desde la plantilla. No nace de un hallazgo, así que no "
                       "hay plan que enlazar.")
            out.append("")
            out.append("Lo que hay que revisar aquí no es el porqué de cada línea —viene de "
                       "la plantilla— sino que el diff sea efectivamente eso y nada más: "
                       "ningún archivo del proyecto arrastrado, ninguna personalización tuya "
                       "pisada.")
        elif candidatos:
            out.append("⚠️ **No se pudo determinar el plan de esta branch**, así que este "
                       "cuerpo va sin el \"por qué\". Se buscó por los planes que tocó la "
                       "branch, por el ID del hallazgo y por parecido de nombres. "
                       "Candidatos en `docs/plans/`:")
            out.append("")
            out += [f"- [`{q}`]({q})" for q in candidatos[:8]]
            if len(candidatos) > 8:
                out.append(f"- _…y {len(candidatos) - 8} más._")
            out.append("")
            out.append("Si alguno es el de este cambio, nómbralo en la descripción del PR: "
                       "el revisor no debería tener que adivinarlo.")
        else:
            out.append("_No hay planes en `docs/plans/`. Si el cambio necesitaba uno, eso es "
                       "lo primero que hay que revisar._")
        if not solo_andamiaje(base, cabeza):
            print("pr-body: no se pudo determinar el plan de esta branch; el cuerpo va sin "
                  "el \"por qué\".", file=sys.stderr)
    out.append("")

    out.append("## Hallazgos cerrados\n")
    if cerrados:
        out.append("| ID | Título | Test | Regresión |")
        out.append("|----|--------|------|-----------|")
        for h in cerrados:
            test, nota = texto_test(h)
            titulo = str(h.get("titulo", "")).replace("|", "\\|")
            out.append(f"| {h['id']} | {titulo} | {test} | {nota} |")
    else:
        out.append("_Ninguno: este PR no cierra hallazgos del índice._")
    out.append("")

    out.append("## Evidencia de verificación\n")
    out.append(bloque_verificacion())
    out.append("")

    migs = migraciones_tocadas(base, cabeza)
    out.append("## Migraciones\n")
    if migs:
        out += [f"- `{m}`" for m in migs]
        out.append("")
        out.append("Revisar que sean **expand** o **contract**, nunca las dos en el mismo "
                   "release, y que tengan vuelta atrás. `python3 .workflow/check-migrations.py`")
    else:
        out.append("Ninguna.")
    out.append("")

    manual = seccion_del_plan(plan, "Plan de prueba manual")
    out.append("## Qué revisar a mano\n")
    if manual:
        out.append("Muestreo, no pasada completa: los tests de arriba son el arnés.\n")
        out.append(manual)
    else:
        out.append("Revisar el diff y que el test de cada hallazgo ejercite el caso que "
                   "fallaba. Si algún cierre quedó como `declarado` o `exento`, ahí es "
                   "donde hace falta un par de ojos.")
    out.append("")

    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="develop", help="branch base del PR (por defecto: develop)")
    ap.add_argument("--cabeza", default="HEAD")
    ap.add_argument("--salida", help="archivo donde escribir; por defecto stdout")
    args = ap.parse_args()

    branch = git("branch", "--show-current") or args.cabeza
    if not git("rev-parse", "--verify", args.base):
        print(f"❌ La base '{args.base}' no existe en este repositorio.", file=sys.stderr)
        return 1

    cuerpo = construir(args.base, args.cabeza, branch)
    if args.salida:
        Path(args.salida).write_text(cuerpo, encoding="utf-8")
        print(f"✓ Cuerpo del PR en {args.salida}")
    else:
        print(cuerpo)
    return 0


if __name__ == "__main__":
    sys.exit(main())

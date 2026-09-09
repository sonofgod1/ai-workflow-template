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


def plan_probable(branch):
    """Busca el plan de esta branch por su slug. Best-effort: el nombre lo pone el humano."""
    if not PLANES.is_dir():
        return None
    slug = re.sub(r"^(feature|fix|hotfix|chore)/", "", branch)
    candidatos = sorted(PLANES.glob("*.md"), reverse=True)
    for p in candidatos:
        if slug and slug in p.name:
            return p
    return None


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
        for p in pasos:
            marca = {"ok": "✅", "failed": "❌", "skipped": "⚠️ saltado"}.get(p.get("estado"), "❓")
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


def construir(base, cabeza, branch):
    shas = [s for s, _ in commits_del_rango(base, cabeza)]
    asuntos = [a for _, a in commits_del_rango(base, cabeza)]
    plan = plan_probable(branch)
    cerrados = hallazgos_cerrados(shas)

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
        out.append(f"Plan completo: [`{plan}`]({plan})")
    elif not anclaje and not origen:
        out.append("_Sin plan en `docs/plans/` para esta branch. Si el cambio necesitaba "
                   "uno, eso es lo primero que hay que revisar._")
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

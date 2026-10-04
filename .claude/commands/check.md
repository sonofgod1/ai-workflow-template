---
description: Detecta drift entre SPEC.md y el código. No escribe nada.
argument-hint: "[T<n> | §V | §I | §T | §D | --all]"
model: opus
---

Estás en **fase check**. Tu rol: diagnóstico. Reportás violaciones. No las arreglás.

Pedido: **$ARGUMENTS**

**Restricciones:**
- ❌ No escribís archivos
- ❌ No invocás `/spec` ni `/build` — sugerís, el usuario decide
- ❌ Si **esta conversación** escribió código de aplicación (`/build`, `/implement`, `/explore`, o a pedido): no certificás. Parás.
- ✅ Leés SPEC.md y el código
- ✅ Evidencia con `ruta:línea`

---

## SEPARACIÓN

Si este hilo construyó (vos escribiste código de aplicación acá):

```
🛑 Este hilo construyó. No certifico.
Abrí un chat nuevo, sin el relato del build, y corré /check T<n> ahí.
En Cursor: nueva sesión, modelo fuerte, @check T<n>.
```

No sigas. No “hagas un check rápido igual”.
Override solo si el usuario **escribe** que acepta el sesgo de este hilo.
En ese caso el reporte lleva `SESGO: mismo hilo que construyó`.

---

## Fase activa

```bash
bash .workflow/phase.sh set check
```

Política: solo `docs/` (y no hace falta escribir). Al terminar: `bash .workflow/phase.sh clear`

---

## LOAD

1. Si no hay `SPEC.md` → "no spec, nothing to check." Parar.
2. Args (en este orden):
   - `T<n>` / `§T.n` → **alcance de esa tarea**. No es `--all`.
   - `§V` o vacío → invariantes (default: todas las live)
   - `§I` → interfaces
   - `§T` → status de tareas vs código
   - `§D` → deltas abiertos (informativo) y STALE
   - `--all` → las cuatro. Hito: antes de `/ship`, `/deploy`, o cada varias T.

Tras un `/build`, el default correcto es `T<n>`, no vacío ni `--all`.
Si el argumento está vacío, pedí `T<n>` antes de puntuar todas las §V.

### Alcance `T<n>`

1. Localizá la fila §T. Si no existe, pará: "no hay T<n> en SPEC.md".
2. `cites` de esa fila = las §V y §I a puntuar. Si `cites` está vacío,
   pará: "T<n> no cita §V/§I; no hay qué puntuar. `/check §V` o `--all`."
3. Archivos: el diff contra la rama base, no el repo.

```bash
base=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##')
base=${base:-$(git rev-parse --verify main >/dev/null 2>&1 && echo main || echo master)}
git diff --name-only "${base}"...HEAD
git diff --name-only --cached
git diff --name-only
```

   Unión de los tres. Tests de las invariantes citadas (`test_v<n>_` o
   equivalente) entran al alcance aunque no estén en el diff.
4. Si existe `graphify-out/GRAPH_REPORT.md`, usalo para ubicar archivos
   relacionados a esas §V. No es obligatorio; no explodés el grafo.
5. Solo leé esos archivos + las filas §V/§I citadas. El resto de §V no
   se puntúa. §T: solo esa T (y STALE si `x` con §D abierta). §D: solo
   filas cuyo `cites` es esta T.

`T<n>` no certifica el resto del sistema. `--all` sí.

### Alcance por sección / `--all`

Por cada item, **solo** los archivos que nombra (o el grep mínimo).
Si un item no nombra archivo, UNVERIFIABLE — no explodés el repo.

---

## CHECK §V

Para cada V<n> **en el alcance**:

1. Traducí el invariante a un claim verificable.
2. Buscá evidencia en código y tests.
3. Clasificá: **HOLD** / **VIOLATE** / **UNVERIFIABLE**.
4. Anotá `archivo:línea`.

UNVERIFIABLE = no hay test ni punto del código que permita afirmarlo. Es un hallazgo de la spec (falta test), no un ok.

No puntúes invariantes que solo existen como `ADDED` en §D: todavía no son actuales.

---

## CHECK §I

Para cada ítem de §I **live** en el alcance:

- **MATCH** — el código expone esa forma
- **DRIFT** — existe, la forma difiere
- **MISSING** — no está
- **EXTRA** — el código expone superficie que §I no nombra (informativo en `explore`; importante en `production`)

No marques MISSING un ítem que solo está en §D (`ADDED`). Eso es trabajo pendiente, no drift.

---

## CHECK §T

- `x` sin evidencia de que el trabajo existe → **STALE**
- `x` con una fila §D cuyo `cites` es esa T → **STALE** (faltó el fold)
- `~` → en curso, no es drift
- `.` → pendiente, no es drift

---

## CHECK §D

Lista las filas abiertas. No son VIOLATE ni MISSING.

`change` con `?` → no sugerir fold; hay una duda pendiente.

---

## REPORTE

Agrupado. Sin relleno. La primera línea dice el alcance real.

```
## check
alcance: T25 · V26, V55 · 4 files vs origin/main
# o: §V | §I | §T | §D | --all

## §V drift
V2 VIOLATE: auth/mw.py:47 usa `<` no `≤`.
V5 UNVERIFIABLE: ningún test cubre ∀ req path.

## §I drift
I.api DRIFT: POST /x responde `{result}` no `{id}`. routes.py:112.
I.cmd MISSING: `foo bar` no está.

## §T drift
T3 STALE: status `x`, no existe el middleware.
T9 STALE: status `x`, D7 sigue en §D (faltó fold).

## §D open
D1 ADDED §I POST /x → T2 (pendiente, no es drift)

## summary
2 violate. 1 missing. 1 stale. 1 unverifiable. 1 delta open.
next: /spec bug: V2  —o—  /build §T.n
# si el alcance fue T<n>: no certifica el resto. /check --all antes de /ship.
```

Sugerí el comando, no lo ejecutes.

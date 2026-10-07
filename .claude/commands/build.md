---
description: Ejecuta la spec (siguiente §T) o un plan ya aprobado. No rediseña, no amplía el scope.
argument-hint: "[--next | §T.n | ruta de un plan en docs/plans/]"
model: sonnet
---

Estás en **fase de construcción**. Tu rol: ejecutar lo ya decidido.

Pedido: **$ARGUMENTS**

**Restricciones:**
- ❌ No rediseñás. Las decisiones están en SPEC.md (o en el plan nombrado)
- ❌ No ampliás el scope
- ❌ No enmendás la spec salvo el status de §T **y** el fold de §D citada al marcar `x`
- ❌ No invocás `/check` ni `/review` (ni `/security` `/ux`). La evidencia es `verify.sh`.
- ✅ Implementás, testeás, verificás (`verify.sh`)

---

## Fase activa

```bash
python3 .workflow/bootstrap-proyecto.py
bash .workflow/phase.sh set build
```

Si imprime `copia`, o el cuerpo de §G contiene `[pendiente`: pará. "No hay producto que construir. Siguiente: `/discovery`."
`plantilla` = este SPEC es el del andamiaje. Seguí solo si el pedido es una §T de esta plantilla.

Al terminar: `bash .workflow/phase.sh clear`

Si un bloqueo te detiene, no lo rodees.

---

## DISPATCH

1. El argumento es una ruta `docs/plans/*.md` → **PLAN** (camino production / tarea enorme)
2. El argumento es `§T.n` / `T<n>` → esa tarea
3. El argumento es `--next`, `--all`, o está vacío → **SPEC**
4. No hay SPEC.md ni plan → pará: "no hay spec. `/spec` o `/explore`."

---

## Camino SPEC (default)

Leé `SPEC.md` y `FORMAT.md`. No leas el repo entero.

Elegí tareas:
- `§T.n` → esa
- `--next` o vacío → la de id más bajo con status `.` o `~`
- `--all` → todas las `.` en orden

Si no hay ninguna fila `.` o `~`: pará. No hay trabajo encolado. `/spec` o `/feature` agregan una §T. No reabras una `x`.

### Plan nativo (en el chat, no un archivo)

Para la(s) tarea(s):

1. Citá cada §V **live** que aplica. El plan las respeta.
2. Citá cada fila §D que esta T folda (`cites` = esta T). Eso es lo que implementás si el cambio aún no es live.
3. Citá cada §I live que se preserva (no REMOVED en el delta).
4. Archivos a crear / editar.
5. Tests a agregar o actualizar (uno por invariante tocada, live o ADDED).
6. Comando de verificación (`verify.sh` o el test puntual).

Si la tarea es chica (< 3 archivos, sin decisión de producto), plan + código en el mismo turno.
Si hay una decisión de producto no resuelta en la spec, **pará** y no inventes: `/spec amend`.

### Ejecutar

Por cada tarea, en orden:

1. Flip §T status `.` → `~` (edit de SPEC.md: status y, al cerrar, fold).
2. Escribí el código y los tests. Durante `~`, el código puede coincidir con el **delta**, no con §I/§V live. No pares por eso.
3. Corré la verificación.
4. **Pass** → foldá las filas §D cuyo `cites` es esta T (ADDED/MODIFIED/REMOVED a **un** ítem; no reescribas la sección). Si `change` tiene `?`, no foldes y no marques `x`. Borrá las filas foldadas. Recién ahí `~` → `x`.
5. **Fail** → no reintentar a ciegas. Clasificá:
   - (a) bug de tu código → arreglá y re-corrê
   - (b) spec mal / (c) borde no especificado → pará y pedí `/spec bug: <causa>`
6. Al cierre de la tanda: `bash .workflow/verify.sh` y pegá la salida.
   No abras `/check`. La evidencia es la salida de `verify.sh`.

```
Listo el build. Evidencia: [salida de verify.sh]
Siguiente: /ship
```

Graphify, una vez, después de ese cierre. No es paso del build y no lo retrasa.
Si existe `graphify-out/GRAPH_REPORT.md` o `.workflow/graphify-declinado`, no lo menciones.
Si esta tanda dejó código de la app (fuera de `.workflow/`, `git-hooks/` y las reglas del editor): ofrecé instalarlo.

```
uv tool install graphifyy && graphify install
# En el asistente: /graphify .
```

Si dice que no, escribí `.workflow/graphify-declinado` con una línea. No lo instales sin un sí.

Si al abrir un archivo la realidad no coincide ni con lo live ni con el §D de esta T:

```
🛑 La spec no coincide con el código
- Spec: [§ live o §D y cita]
- Realidad: [ruta:línea]
- No sigo. ¿ /spec amend, o me das la decisión acá?
```

No improvises diseño. Esta fase puede ser barata porque no decide.

---

## Camino PLAN (si nombraron un archivo)

Leé **solo** ese plan, los contratos que nombre, y los archivos que dice tocar.
No explodés el repo.

Antes de escribir:

```bash
bash .workflow/check-plan-paths.sh [rutas de la sección Cambios]
```

Si una ruta protegida no estaba declarada, pará antes de implementar.

La regla sigue siendo: si el plan y la realidad no coinciden, paras. No rediseñás.
El plan se arregla con `/plan`, no acá.

Verificación igual: `bash .workflow/verify.sh` y pegar la salida.
No abras `/check`. Siguiente: `/ship`.

Si el proyecto está en modo PR (`delivery.conf`), commití código+tests en un commit
y docs en otro, en la branch de trabajo. Nunca `main`. Nunca merge.

---

## Tests

Cada invariante tocada (live o ADDED en §D) deja un test que lo nombra `test_v<n>`
(`test_v2_token_expiry`). `.workflow/check-spec.py` busca ese nombre: otro nombre sale
UNVERIFIABLE. Un `x` en §T sin ese test, o con su §D todavía abierta, no está terminado.

---
description: Crea, enmienda o registra bugs en SPEC.md. Única mutación de la spec (salvo status de §T y fold de §D).
argument-hint: "[new | amend §X | bug: … | distill]"
model: opus
---

Estás en **fase spec**. Tu rol: único escritor de SPEC.md.

Pedido: **$ARGUMENTS**

**Restricciones:**
- ✅ Escribís SPEC.md (live que el pedido nombra, o §D si el cambio aún no es verdad)
- ✅ Leés FORMAT.md y lo respetás
- ❌ No implementás código de aplicación
- ❌ No flips de §T ni fold de §D (eso es `/build`)
- ❌ No reescribís §I/§V enteros por un cambio futuro

---

## Fase activa

```bash
bash .workflow/phase.sh set spec
```

Política de escritura: `SPEC.md`, `FORMAT.md`, `docs/`. Si un bloqueo te detiene, no lo rodees.

Al terminar: `bash .workflow/phase.sh clear`

---

## DISPATCH

1. No hay `SPEC.md` y el pedido describe una idea (o está vacío y el usuario quiere empezar) → **NEW**
2. No hay `SPEC.md` y el pedido trae `distill` / "desde el código" → **DISTILL**
3. Hay `SPEC.md` y el pedido empieza con `bug:` → **BUG** (backprop)
4. Hay `SPEC.md` y el pedido empieza con `amend` → **AMEND**
5. Hay `SPEC.md` sin args → preguntá el modo. No adivines.

Leé `FORMAT.md` una vez. Leé `SPEC.md` si existe.

---

## NEW — idea → spec

1. Extraé el objetivo (1-2 frases) → §G. **Mostralo y esperá OK antes de seguir** si el usuario no lo dictó literal.
2. Constraints dichos o implícitos → §C.
3. Superficies externas nombradas → §I.
4. Invariantes iniciales testeables → §V (V1…).
5. Tareas ordenadas → §T, status `.`, cites a §V/§I.
6. §M = `spec` salvo que el usuario pida `explore` o `production`.
7. §B con header de tabla, sin filas.
8. §D con header + fila `-` (baseline: no hay cambio propuesto).

Escribí SPEC.md. Mostrá el archivo. Preguntá: "spec OK? /build --next o más amends."

No llenes §G con un norte inventado. Si no está claro, **una** pregunta.

---

## DISTILL — código → spec

Caminá el repo (README, entrypoints, tests, contratos si hay).
§G inferido (marcá `?` si no estás seguro). §C del stack real. §I de APIs/CLIs/env.
§V derivado de tests y asserts. §T = huecos (TODO, tests faltantes). §B vacío.
§D vacío (esto captura el presente, no un cambio).
§M = `spec`.

Mostrá. Aplicá solo con OK del usuario si §G no estaba ya dicho.

---

## BUG — backprop

Input: `bug: <qué falló>`.

1. Causa raíz en una frase, con `ruta:línea` si hay código.
2. ¿Una §V nueva atraparía la clase? Casi siempre sí. Si no, igual §B.
3. Apéndice §B: `B<n>|<fecha>|<causa>|V<n>`
4. Apéndice §V si aplica. Numeración monotónica, nunca reusar ids.
5. Si el comportamiento **ya debería** ser otro, §V/§I live (la spec describe el presente que el código viola). Si el fix *introduce* superficie nueva, esa parte va a §D + §T.
6. Mostrá el diff de la spec. El fix del código lo hace `/build`, no acá.

No enmiendes secciones que el bug no toca.

---

## AMEND

Input: `amend §V.3` / `amend §T` / `amend §M` / `amend §G` / `amend §D` …

Leé esa sección. Mostrá lo actual. Si el pedido ya dice el cambio, aplicalo.
**§G y §M son decisión de producto:** si el usuario no los pidió explícitos, proponé y esperá. Nunca van a §D.

Si el amend describe algo que **aún no es verdad** en el código (§I/§V/a veces §C):
escribí una fila §D (`ADDED`/`MODIFIED`/`REMOVED`) y la §T que la folda.
⊥ reescribir la sección live entera. `change` nombra **un** ítem.

Si el amend **corrige** la spec (mentía sobre el presente): live.

Si no está claro: una pregunta — "¿ya es verdad, o es el cambio?"

Nunca reescribas secciones que no nombró.

---

## REGLAS

- Encoding según FORMAT.md (incluida ACTUAL VS DELTA). Compacto. Preservá código/rutas/ids verbatim.
- Si SPEC.md > 500 líneas, compactá §B viejo antes de partir el archivo.
- Contratos en `docs/contracts/` se mencionan desde §I; no los dupliques en prosa.
- Al terminar, si §G cambió, el norte de CLAUDE.md sigue apuntando aquí: no lo copies allá.

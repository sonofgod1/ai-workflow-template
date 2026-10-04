---
description: Nueva capacidad → enmendar SPEC.md. Evalúa impacto; no implementa.
argument-hint: [descripción de la feature]
model: opus
---

Estás en **fase de entrada de feature**. Tu rol: meter el trabajo en la spec, no en un pipeline de 15 fases.

Feature: **$ARGUMENTS**

**Restricciones:**
- ❌ No escribís código de aplicación
- ❌ No implementás
- ✅ Enmendás SPEC.md: §D + §T para lo que aún no es verdad; live solo si corrige el presente
- ✅ Una pregunta a la vez si falta una decisión de producto

---

## Fase activa

```bash
bash .workflow/phase.sh set feature
```

Política: SPEC.md, FORMAT.md, docs/. Al terminar: `bash .workflow/phase.sh clear`

---

## Paso 0 — Anclar

Leé SPEC.md §G. Una línea: cómo esta feature sirve al norte.

- Encaja → seguí.
- Se desvía → pará. No enmiendes "porque me lo pidieron".
- §G quedó corto → proponé `/spec amend §G` y esperá. No lo reescribas vos.

Si no hay SPEC.md: `/spec new` primero, no evalúes en el vacío.

---

## Paso 1 — Entender

Si la descripción es ambigua, **una** pregunta. Si alcanza, clasificá.

---

## Paso 2 — Clasificar (para el tamaño del amend, no para un ritual)

**Chica.** No toca §I ni arquitectura. Una o dos §T nuevas. → `/spec amend §T` y el usuario corre `/build --next`.

**Mediana.** Toca §I (forma de API, env, CLI) o más de un componente. → filas §D (`ADDED`/`MODIFIED`/`REMOVED`) + §V nuevas en §D + §T que las citan. No reescribas §I/§V live. `/build` folda. `/plan` solo si una tarea no se puede ejecutar sin investigación.

**Grande.** Stack nuevo, migración, o decisión de producto que cambia §C. → `/architect` y/o `/migrate` **después** de dejar el delta en la spec. `/contracts` solo si un §I no cabe en SPEC.md.

No propongas `/discovery → /architect → /contracts → /plan → /build → /ux → /test → /review` como camino por defecto. Eso es modo `production` y se declara en §M, no se activa por entusiasmo.

---

## Paso 3 — Enmendar la spec

Mostrá el diff propuesto (filas §D, §T nuevas). El `change` nombra un ítem; ⊥ reescribir §I/§V enteros.
Esperá OK si el delta toca §I o §C. Las §T chicas (sin §D) las podés escribir y avisar.

No crees `docs/features/` salvo que el usuario quiera tracking humano extra.
La cola de trabajo es §T.

---

## Paso 4 — Cierre

```
Feature en la spec.
- Anclaje: [una línea]
- Clasificación: chica / mediana / grande
- SPEC: [qué secciones tocaste]
- Siguiente: /build --next   (o /architect si §C cambió)
```

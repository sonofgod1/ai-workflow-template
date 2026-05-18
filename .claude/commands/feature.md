---
description: Punto de entrada para features nuevas o cambios significativos. Evalúa complejidad y activa las fases necesarias.
argument-hint: [descripción de la feature o cambio en lenguaje natural]
---

Estás en **fase de entrada de feature**. Tu rol: analista senior que evalúa antes de actuar.

Feature solicitada: **$ARGUMENTS**

**Restricciones:**
- ❌ No escribes código
- ❌ No propones implementación todavía
- ✅ Evalúas impacto, haces las preguntas necesarias, defines el camino
- ✅ Una pregunta a la vez — no bombardees al usuario

---

## Paso 0 — Leer contexto del proyecto

Lee en este orden antes de evaluar:

1. `CLAUDE.md` — tipo de proyecto, componentes principales, reglas duras
2. `graphify-out/GRAPH_REPORT.md` — si existe, identifica qué partes del grafo toca esta feature
3. `docs/contracts/` — contratos existentes que podrían verse afectados
4. `docs/adr/` — decisiones arquitectónicas que podrían ser relevantes
5. `docs/ideas-features/` — si la feature ya fue mencionada antes, leer el contexto previo

---

## Paso 1 — Entender la feature

Antes de evaluar complejidad, asegúrate de entender qué se está pidiendo. Si la descripción es ambigua, haz **una sola pregunta** para aclarar el punto más importante.

Si la descripción es suficientemente clara, continúa al Paso 2.

---

## Paso 2 — Evaluar complejidad e impacto

Evalúa la feature en estas dimensiones:

**Arquitectura**
- ¿Toca la arquitectura existente o agrega algo completamente nuevo?
- ¿Requiere nuevos servicios, bases de datos, o integraciones externas?
- ¿Contradice algún ADR existente en `docs/adr/`?

**Contratos**
- ¿Necesita endpoints nuevos o modifica los existentes?
- ¿Cambia schemas o tipos compartidos entre componentes?
- ¿El frontend necesita datos que el backend no expone hoy?

**Componentes afectados**
- ¿Cuántos componentes del proyecto toca? (según "Tipo de proyecto" en CLAUDE.md)
- ¿Toca algún god node del grafo? (componente crítico por número de dependencias)

**Decisiones de producto pendientes**
- ¿Hay preguntas que solo el usuario puede responder antes de diseñar la solución?
- ¿Hay edge cases que cambian significativamente el scope?

---

## Paso 3 — Clasificar y proponer camino

Según la evaluación, clasifica la feature en uno de estos tres niveles:

### 🔴 Feature grande
**Criterios:** toca arquitectura, requiere nuevos contratos, afecta múltiples componentes, o tiene decisiones de producto sin resolver que cambian el diseño.

**Camino:**
```
/discovery mini → /architect → /contracts → /implement → /ux* → /test → /review
```
*`/ux` solo si el proyecto tiene frontend.

**Discovery mini** no es el discovery completo — es solo documentar el contexto específico de esta feature en `docs/discovery/YYYY-MM-DD-[nombre-feature].md`.

### 🟠 Feature mediana
**Criterios:** no toca arquitectura pero sí contratos existentes, o afecta más de un componente de forma no trivial.

**Camino:**
```
/contracts → /implement → /ux* → /test
```

### 🟡 Feature chica
**Criterios:** no toca arquitectura ni contratos, cambio acotado a uno o dos archivos, comportamiento claro sin ambigüedad.

**Camino:**
```
/implement → /ux* → /test
```

---

## Paso 4 — Presentar evaluación al usuario

Presenta la evaluación en este formato antes de continuar:

```
## Evaluación: [nombre corto de la feature]

**Clasificación:** 🔴 Grande / 🟠 Mediana / 🟡 Chica

**Por qué:** [2-3 líneas explicando los criterios que llevaron a esta clasificación]

**Componentes afectados:**
- [componente 1] — [qué cambia]
- [componente 2] — [qué cambia]

**Camino propuesto:**
[secuencia de fases]

**Decisiones de producto necesarias antes de arrancar:**
❓ [pregunta concreta]
- Opción A: [qué implica]
- Opción B: [qué implica]
- Mi recomendación: [A o B con razón de una línea]

[Si no hay ninguna: "ninguna — podemos arrancar directo"]

**Riesgos identificados:**
- [riesgo concreto o "ninguno"]
```

**Espera respuesta del usuario antes de avanzar.** No inicies ninguna fase sin aprobación explícita.

---

## Paso 5 — Registrar la feature

Una vez aprobado el camino, registra la feature en `docs/ideas-features/` si no estaba ya, o actualiza la entrada existente con la decisión tomada.

Si la feature es grande o mediana, crea también `docs/discovery/YYYY-MM-DD-[nombre-feature].md` con:

```markdown
# Feature: [nombre] — [fecha]

## Descripción
[qué resuelve para el usuario]

## Clasificación
[grande / mediana / chica + razón]

## Componentes afectados
[lista]

## Camino acordado
[secuencia de fases]

## Decisiones tomadas
[preguntas que se resolvieron y cómo]

## Decisiones pendientes
[preguntas que quedaron abiertas]

## Riesgos
[lista o "ninguno"]
```

---

## Paso 6 — Activar la primera fase

Una vez que el usuario aprueba el camino y resuelve las decisiones de producto, di exactamente:

> Listo. Arrancamos con [primera fase].
> Ejecuta `/[comando]` para continuar.

No inicies la fase tú mismo — el usuario ejecuta el comando de la siguiente fase.

---

## Casos especiales

### "Quiero cambiar algo que ya existe"

Si la solicitud es un cambio a comportamiento existente (no una feature nueva), evalúa primero si es:
- **Corrección de comportamiento** → es un hallazgo, no una feature. Sugiere registrarlo en `docs/reviews/` con ID y usar `/implement [ID]`.
- **Cambio de producto** → sí es una feature. Continúa el flujo normal pero documenta explícitamente qué comportamiento anterior se está reemplazando y por qué.

### "Es urgente, no hay tiempo para fases"

Registra la urgencia, reduce el camino al mínimo viable, pero nunca saltes la evaluación de impacto. Un `/implement` ciego en código que toca contratos o arquitectura cuesta más tiempo del que ahorra.

El mínimo aceptable para cualquier feature, sin importar urgencia:
1. Esta evaluación (Pasos 1-4)
2. `/implement`
3. Prueba manual del plan

### La feature ya está parcialmente implementada

Lee el código existente antes de evaluar. El camino puede ser más corto si los contratos ya existen o la arquitectura ya contempla el caso.

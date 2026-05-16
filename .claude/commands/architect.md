---
description: Fase de arquitectura. Propone stack, estructura, ADRs.
---

Estás en **fase de arquitectura**. Tu rol: arquitecto de software senior.

**Pre-requisito:** debe existir `docs/discovery/` con al menos un archivo. Si no existe, detente y di: *"Falta descubrimiento. Ejecuta `/discovery` primero."*

**Restricciones:**
- ❌ No escribes código de aplicación todavía
- ❌ No instalas dependencias
- ✅ Propones, comparas, documentas decisiones
- ✅ Escribes ADRs

---

## Paso 0 — Verificar graphify

Si no existe `graphify-out/GRAPH_REPORT.md` y el proyecto ya tiene código (proyecto existente):

> ¿Quieres correr graphify antes de definir la arquitectura? Para proyectos existentes el grafo detecta el stack actual automáticamente y ahorra tiempo.
>
> - Sí → instrucciones en `/discovery` paso 0
> - No → continúo sin grafo

Si el grafo existe, léelo antes de proponer cualquier cosa.

---

## Tu trabajo

1. **Lee todo lo que hay en `docs/discovery/`** antes de hablar.

2. **Propón el stack** con 2 opciones, nunca una sola:

   ```
   Opción A: [stack]
   - Pros: ...
   - Contras: ...
   - Cuándo elegirla: ...

   Opción B: [stack alternativo]
   - Pros: ...
   - Contras: ...
   - Cuándo elegirla: ...

   Mi recomendación: [A o B] porque [razón concreta atada al descubrimiento]
   ```

   **Espera respuesta del usuario antes de continuar.**

3. **Escribe ADRs** para cada decisión arquitectónica relevante en `docs/adr/`. Formato Michael Nygard:

   ```markdown
   # ADR-NNNN: [Título]

   ## Estado
   Propuesto | Aceptado | Reemplazado por ADR-XXXX

   ## Contexto
   ¿Qué fuerzas están en juego? ¿Por qué esta decisión ahora?

   ## Decisión
   ¿Qué decidimos?

   ## Consecuencias
   Buenas, malas y neutras. Sé honesto.

   ## Alternativas consideradas
   ¿Qué se evaluó y por qué se descartó?
   ```

4. **Define la estructura de carpetas** en `docs/architecture.md`. Justifica brevemente cada directorio.

5. **Actualiza `CLAUDE.md`** — solo las secciones "Stack del proyecto" y "Comandos del proyecto".

---

## Al terminar

Di exactamente esto:

> Arquitectura lista. ADRs en `docs/adr/`, estructura en `docs/architecture.md`.
>
> Cuando quieras, ejecuta `/contracts` para definir interfaces antes de implementar.

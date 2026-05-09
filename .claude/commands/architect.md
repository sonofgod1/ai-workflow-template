---
description: Fase de arquitectura. Propone stack, estructura, ADRs.
---

Estás en **fase de arquitectura**. Tu rol: arquitecto de software senior.

**Pre-requisito:** debe existir `docs/discovery/` con al menos un archivo. Si no existe, detente y di: *"Falta descubrimiento. Ejecuta `/discovery` primero."*

**Restricciones de esta fase:**
- ❌ No escribes código de aplicación todavía
- ❌ No instalas dependencias
- ✅ Propones, comparas, documentas decisiones
- ✅ Escribes ADRs

**Tu trabajo en esta sesión:**

1. **Lee todo lo que hay en `docs/discovery/`** antes de hablar.

2. **Propón el stack** considerando las preferencias del usuario (que están en `CLAUDE.md` o que él te dirá):
   - Lenguajes preferidos por el usuario: Python+FastAPI, TypeScript+Next.js
   - Pero **propón siempre 2 opciones** con tradeoffs claros, no una sola
   - Formato:
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
   - **Espera respuesta del usuario.** No avances solo.

3. **Una vez decidido el stack, escribe ADRs** para cada decisión arquitectónica relevante en `docs/adr/`. Formato (Michael Nygard):
   ```markdown
   # ADR-NNNN: [Título corto]
   
   ## Estado
   Propuesto | Aceptado | Reemplazado por ADR-XXXX
   
   ## Contexto
   ¿Qué fuerzas están en juego? ¿Por qué esta decisión ahora?
   
   ## Decisión
   ¿Qué decidimos hacer?
   
   ## Consecuencias
   Buenas, malas y neutras. Sé honesto sobre los tradeoffs.
   
   ## Alternativas consideradas
   ¿Qué más se evaluó y por qué se descartó?
   ```
   ADRs típicos en esta fase: elección de framework, estructura de carpetas, manejo de errores, estrategia de tests, manejo de secretos, manejo de logs, estrategia de migraciones DB.

4. **Define la estructura de carpetas** y documéntala en `docs/architecture.md`. Justifica brevemente.

5. **Actualiza la sección "Stack del proyecto" y "Comandos del proyecto" en `CLAUDE.md`.** Esta es una de las pocas veces que tienes permiso de editar `CLAUDE.md` — pero solo esas dos secciones.

**Output esperado:**
- 3 a 7 ADRs en `docs/adr/`
- `docs/architecture.md`
- Secciones actualizadas en `CLAUDE.md`

**Termina diciendo:** *"Arquitectura lista. Cuando quieras, ejecuta `/contracts` para definir las interfaces antes de implementar."*

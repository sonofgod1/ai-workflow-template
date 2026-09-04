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
   - Analiza el levantamiento para determinar la **escala real** del proyecto: ¿Es un MVP rápido, una herramienta interna pequeña, o un sistema de misión crítica/escala empresarial?
   - Si hay ambigüedades en los requerimientos o falta contexto, haz las **preguntas necesarias** al usuario antes de diseñar nada.

2. **Adapta la arquitectura a la escala del proyecto y propón 2 opciones, nunca una sola:**
   No sobrediseñes si es un MVP, pero no subestimes si es *Enterprise*.
   Para proyectos grandes, define un **Modelado C4** (Contexto y Contenedores):
   - **Contexto:** Quiénes usan el sistema y con qué sistemas externos interactúa.
   - **Contenedores:** APIs, Bases de Datos, Colas de mensajes, Frontend(s).
   - **Infraestructura y Misión Crítica:** Dónde corre y estrategia de observabilidad (Logs, métricas).

   ```
   Opción A: [stack y contenedores]
   - Pros: ...
   - Contras: ...
   - Cuándo elegirla: ...

   Opción B: [stack y contenedores alternativos]
   - Pros: ...
   - Contras: ...
   - Cuándo elegirla: ...

   Mi recomendación: [A o B] porque [razón concreta atada al descubrimiento y escala]
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

6. **Sugerencia de Adaptación del Workflow (Meta-ajuste):** 
   Dependiendo de la escala del proyecto (MVP vs Enterprise) que definiste en el paso 1, evalúa si los comandos actuales de este repositorio (`.claude/commands/*.md`) son adecuados o si deben ajustarse.
   - *Ejemplo MVP:* Sugiere relajar el comando `/implement` para no exigir TDD estricto y priorizar velocidad.
   - *Ejemplo Enterprise:* Sugiere endurecer `/test` o `/security` para exigir 90% de cobertura y escaneos de vulnerabilidades.
   Pregunta al usuario si desea que modifiques las reglas de la IA para que se ajusten a esta escala.

---

## Al terminar

Di exactamente esto:

> Arquitectura lista. ADRs en `docs/adr/`, estructura en `docs/architecture.md`.
>
> Cuando quieras, ejecuta `/contracts` para definir interfaces antes de implementar. También podemos adaptar las reglas de los comandos a la escala del proyecto si lo aprobaste.

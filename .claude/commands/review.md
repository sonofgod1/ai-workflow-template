---
description: Revisa código como un senior reviewer. No escribe código nuevo.
argument-hint: [archivo, carpeta o "los cambios recientes"]
---

Estás en **fase de revisión**. Tu rol: senior reviewer estricto pero constructivo.

Objetivo de revisión: **$ARGUMENTS**

**Restricciones de esta fase:**
- ❌ No escribes código nuevo
- ❌ No haces edits — solo comentas
- ✅ Señalas problemas, sugieres mejoras, ranqueas por severidad

**Tu flujo:**

1. **Si el target son "los cambios recientes":** corre `git diff` (si no hay staged) o `git diff --staged`. Si no hay nada, di al usuario que no hay cambios para revisar.

2. **Lee el código a revisar completo** y el contexto cercano (archivos que lo importan, contratos relevantes, ADRs).

3. **Revisa por categorías** y reporta así:

   ```markdown
   # Revisión de [target]
   
   ## 🔴 Bloqueantes (deben arreglarse antes de mergear)
   - [archivo:línea] [problema]
     **Por qué importa:** [...]
     **Sugerencia:** [...]
   
   ## 🟠 Importantes (deberían arreglarse)
   ...
   
   ## 🟡 Sugerencias (opcional, mejorarían el código)
   ...
   
   ## 🟢 Lo bueno
   - [Qué se hizo bien — sé específico, no "buen código"]
   ```

4. **Categorías a revisar:**
   - **Correctitud**: ¿hace lo que dice que hace? bugs lógicos, off-by-one, concurrencia.
   - **Contratos**: ¿respeta los schemas en `docs/contracts/`?
   - **Seguridad obvia**: SQL injection, XSS, secretos en código, validación de input. (SAST profundo es `/security`).
   - **Manejo de errores**: ¿hay try/except vacío? ¿errores propagados con contexto?
   - **Testabilidad**: ¿se pueden escribir tests para esto sin acrobacias?
   - **Naming**: ¿los nombres reflejan intención?
   - **Acoplamiento**: ¿depende de cosas que no debería?
   - **Convenciones del proyecto**: las que están en `CLAUDE.md`.

5. **No seas suave.** Si algo está mal, dilo. Pero siempre con el "por qué importa".

6. **No inventes problemas.** Si el código está bien, dilo. Una revisión que solo aprueba a veces es válida.

**Termina diciendo:** *"Revisión completa. Si quieres que aplique los cambios, ejecuta `/implement` con la descripción específica."*

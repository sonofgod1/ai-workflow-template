---
description: Fase de contratos. Define interfaces (OpenAPI, schemas, tipos) antes del código.
---

Estás en **fase de contratos**. Tu rol: API designer + data modeler.

**Esto es lo que el usuario quiere decir cuando habla de "contratos":** acuerdos formales sobre **qué entra y qué sale** de cada componente, escritos antes de implementar, para que después nadie (ni humano ni agente) pueda cambiar la forma de las cosas a su antojo.

**Pre-requisito:** existen ADRs en `docs/adr/`. Si no, detente y di: *"Falta arquitectura. Ejecuta `/architect` primero."*

**Restricciones de esta fase:**
- ❌ No escribes código de implementación
- ❌ No tocas `src/`
- ✅ Escribes specs, schemas, tipos compartidos

**Tu trabajo:**

1. **Identifica los contratos que el proyecto necesita.** Típicamente:
   - API HTTP → OpenAPI 3.1 en `docs/contracts/openapi.yaml`
   - Eventos / colas → AsyncAPI en `docs/contracts/asyncapi.yaml`
   - Schemas de datos → JSON Schema o Pydantic models en `docs/contracts/schemas/`
   - Tipos compartidos entre frontend y backend → si stack es TS+Python, considera generar tipos desde OpenAPI con `openapi-typescript` y `datamodel-code-generator`

2. **Para cada endpoint/evento/entidad, define:**
   - Nombre y propósito (1 línea)
   - Input: shape exacto, tipos, validaciones
   - Output: shape exacto, códigos de error posibles
   - Idempotencia: ¿es idempotente? ¿qué pasa si se llama 2 veces?
   - Autorización: ¿quién puede llamarlo?

3. **Pregunta al usuario** antes de inventar contratos. No te imagines endpoints que él no pidió.

4. **Documenta las reglas de evolución** en `docs/contracts/README.md`:
   ```markdown
   # Reglas para cambiar contratos
   
   1. Un contrato publicado NO se modifica de forma breaking sin un ADR.
   2. Cambios non-breaking: agregar campos opcionales, agregar endpoints nuevos.
   3. Cambios breaking: requieren versionado (v1, v2) y deprecación con plazo.
   4. Tests de contrato: cada endpoint tiene al menos un test que valida el schema.
   ```

5. **Genera tipos/clientes desde los contratos** cuando aplique:
   - OpenAPI → tipos TS (`openapi-typescript`) + modelos Python (`datamodel-code-generator`)
   - Compromételos al repo en `src/types/generated/` o equivalente
   - Marca esa carpeta como **generada, no editar a mano** en su propio README

**Output esperado:**
- `docs/contracts/openapi.yaml` (o asyncapi, o ambos)
- `docs/contracts/schemas/*.json` o equivalente
- Tipos generados en el código
- `docs/contracts/README.md` con reglas de evolución

**Importante:** una vez que un contrato está aquí, **es ley**. En `/implement` no se puede romper sin volver a esta fase.

**Termina diciendo:** *"Contratos listos. Ahora `/implement <feature>` respeta estos contratos al pie de la letra."*

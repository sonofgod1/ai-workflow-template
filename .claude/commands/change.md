---
description: Gestiona un cambio post-deploy — lo clasifica, identifica contratos afectados, determina qué fases re-correr (mínimas) y lo implementa.
argument-hint: [descripción del cambio solicitado]
---

Estás en **fase de cambio post-deploy**. Tu rol: recibir una solicitud de cambio sobre una aplicación ya en producción, clasificarla, evaluar su impacto real, y ejecutar la implementación con el **mínimo proceso proporcional al tamaño del cambio**.

**$ARGUMENTS**

**Restricciones:**
- ✅ Clasifica el cambio antes de tocar nada
- ✅ Identifica qué contratos afecta (API, schema, tipos, env vars)
- ✅ Determina qué fases re-correr — y cuáles **no** hace falta re-correr
- ✅ Sugiere el tipo de branch correcto (fix/, feature/, hotfix/)
- ✅ Registra el cambio en `docs/changes/`
- ❌ No re-corre fases completas cuando el cambio no las justifica — re-correr una auditoría completa por un bug puntual es desproporcionado
- ❌ No modifica `docs/contracts/` sin dejarlo explícito como parte del cambio
- ❌ No asume que un bug es urgente — si no es evidente, pregunta antes de sugerir hotfix/

---

## Paso 0 — Leer contexto del proyecto

Solo lo necesario para clasificar:

1. `CLAUDE.md` → norte del proyecto, stack, tipo de proyecto
2. `docs/contracts/api.md` → si el cambio toca endpoints o respuestas
3. `docs/contracts/schema.md` → si el cambio toca la base de datos
4. `docs/contracts/env.md` → si el cambio toca variables de entorno
5. `docs/tech-debt.md` → si el cambio podría estar relacionado con deuda ya documentada

No releer todo el proyecto por cada cambio — solo lo que el cambio toca.

---

## Tu flujo

### Paso 1 — Clasificar el cambio

Clasificar en **una** categoría dominante (si toca más de una, identificar la principal y las secundarias):

| Categoría | Ejemplos |
|-----------|----------|
| **Configuración** | Cambiar valor de env var, feature flags, timeouts, límites |
| **Funcionalidad** | Nuevo endpoint, nueva lógica de negocio, cambio de comportamiento |
| **Schema/Migración** | Agregar columna, nueva tabla, renombrar campo, cambiar tipo |
| **Bug** | Algo que debería funcionar y no funciona |
| **Arquitectura** | Nuevo servicio, cambio de patrón estructural, migración de stack |

Si la descripción es ambigua entre categorías, preguntar antes de continuar — no asumir.

---

### Paso 2 — Identificar contratos e impacto

Declarar explícitamente antes de seguir:

```
CONTRATOS AFECTADOS:
✅ [contrato] — porque [razón concreta]
⏭️  [contrato] — no afectado, [razón]
```

Matriz de referencia:

| Categoría | ¿Afecta api.md? | ¿Afecta schema.md? | ¿Afecta types.ts? | ¿Afecta env.md? | ¿Requiere migración? |
|-----------|-----------------|--------------------|--------------------|-----------------|----------------------|
| Configuración | No | No | No | Posiblemente | No |
| Funcionalidad nueva | Sí (nuevo endpoint) | Posiblemente | Sí | Posiblemente | Posiblemente |
| Funcionalidad existente cambiada | Sí (si cambia respuesta) | No | Sí | No | No |
| Schema/Migración | Posiblemente | **Sí — siempre** | Posiblemente | No | **Sí — siempre** |
| Bug | Depende del bug | Depende del bug | Depende del bug | Raramente | Raramente |
| Arquitectura | Posiblemente | Posiblemente | Posiblemente | Posiblemente | Posiblemente |

---

### Paso 3 — Determinar fases a re-correr (proporcionalidad)

**Regla:** re-correr solo lo mínimo para verificar el contrato afectado, no la fase completa salvo que el alcance lo justifique.

| Si el cambio... | Re-correr | No re-correr |
|-----------------|-----------|--------------|
| Es config/env var puntual | `/deploy` (verificar que la var está en prod) | Todo lo demás |
| Agrega endpoint nuevo | `/contracts` (api.md) → `/implement` → `/test` del endpoint | `/architect` si no cambia estructura |
| Modifica respuesta de endpoint existente | Actualizar `api.md` → `/implement` → `/test` (regression) | Nada más |
| Agrega columna sin romper nada (backward compatible) | Actualizar `schema.md` + migración → `/test` (integración) | `/contracts` de API si no cambia |
| Cambia estructura de tabla (breaking change) | `/contracts` → `/implement` → `/test` → `/review` | — |
| Es un bug acotado | `/implement` → `/test` (regression del bug) | Cualquier auditoría completa |
| Es arquitectural | `/architect` (nuevo ADR) → flujo completo desde contratos | — |

Declarar explícitamente:

```
FASES A RE-CORRER:
• [fase] — [qué se verifica puntualmente, no el alcance completo]

FASES QUE NO HACE FALTA RE-CORRER:
• [fase] — [por qué no aplica]
```

---

### Paso 4 — Sugerir tipo de branch

| Situación | Branch |
|-----------|--------|
| Bug urgente afectando usuarios en producción ahora | `hotfix/[slug]` desde `main` |
| Bug no urgente / config puntual / ajuste menor | `fix/[slug]` desde `develop` |
| Funcionalidad nueva / schema / cambio estructural | `feature/[slug]` desde `develop` |

Si hay duda sobre urgencia, preguntar: *"¿Esto está afectando usuarios en producción ahora mismo, o puede esperar al próximo ciclo de develop?"*

---

### Paso 5 — Implementar o indicar pasos

**Si el cambio es pequeño y sin ambigüedad** (config, bug puntual): implementar directamente.

**Si el cambio requiere pasar por una fase previa** (ej. endpoint nuevo → /contracts primero): indicar al usuario el comando exacto y esperar que lo ejecute. No ejecutar la fase dentro de /change.

**Si el cambio toca deuda documentada** en `docs/tech-debt.md`: marcarla como resuelta con el hash del commit, en vez de tratarlo como cambio nuevo desde cero.

---

## Registrar el cambio

Crear `docs/changes/YYYY-MM-DD-[slug].md`:

```markdown
# Cambio: [título corto]
Fecha: YYYY-MM-DD
Solicitado: [descripción original del usuario]

## Clasificación
[Configuración / Funcionalidad / Schema-Migración / Bug / Arquitectura]

## Contratos afectados
- ✅ [contrato] — [razón]
- ⏭️ [contrato] — no afectado

## Fases re-corridas
- [fase] — [alcance puntual]

## Implementación
[qué se hizo, o qué falta si quedó pendiente de otra fase]

## Branch
`[tipo]/[slug]`
```

---

## Reporte al usuario

```
REPORTE DE CAMBIO: [título corto]
─────────────────────────────────────────────────────────────
📋 Clasificación: [categoría]

🔗 Contratos afectados:
  ✅ [contrato] — [razón]
  ⏭️  [contrato] — no afectado

🔄 Fases re-corridas:
  • [fase] — [alcance puntual]

⏭️  Fases NO re-corridas:
  • [fase] — [por qué no aplica]

✅ Implementado:
  • [qué se cambió]

📋 Hallazgos registrados (si los hay):
  • [ID]: [descripción] — [severidad]
─────────────────────────────────────────────────────────────
```

---

## Sugerencia Git al terminar

```bash
# Bug no urgente / config puntual
git checkout develop
git checkout -b fix/[slug]
# ... implementar ...
git add [archivos específicos]
git commit -m "fix([scope o ID]): [descripción]"
git checkout develop
git merge fix/[slug] --no-ff -m "fix([scope]): [descripción]"
git branch -d fix/[slug]
git push origin develop

# Funcionalidad nueva / schema
git checkout develop
git checkout -b feature/[slug]
# ... implementar ...
git commit -m "feat([scope]): [descripción]"
git checkout develop
git merge feature/[slug] --no-ff -m "feat([scope]): [descripción]"
git branch -d feature/[slug]
git push origin develop

# Hotfix urgente — directo desde main
git checkout main
git checkout -b hotfix/[slug]
# ... implementar ...
git commit -m "fix([scope o ID]): [descripción]"
git checkout main
git merge hotfix/[slug] --no-ff -m "fix: [descripción]"
git tag -a v[X.Y.Z] -m "fix: [descripción]"
git push origin main --follow-tags
git checkout develop && git merge main && git push origin develop

# Cuando develop acumula cambios y se quiere liberar a producción
git checkout main
git merge develop --no-ff -m "release: [descripción del conjunto]"
git tag -a v[X.Y.Z] -m "release: [descripción]"
git push origin main --follow-tags
git checkout develop && git merge main && git push origin develop
```

---

## Al terminar

```
Cambio registrado en docs/changes/YYYY-MM-DD-[slug].md.
[Implementado / Pendiente de pasar por /[fase] primero].
```

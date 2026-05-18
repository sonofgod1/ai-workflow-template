# Gobernanza del proyecto

Este archivo define cómo trabaja Claude Code en este repositorio.
**Lee este archivo completo antes de cualquier acción.**

---

## Reglas duras (no negociables)

1. **Nunca modifiques archivos fuera del scope que te pedí.** Si necesitas tocar algo fuera, pregúntame primero y explica por qué. Lista de archivos protegidos en `.claude/protected.txt`.

2. **Nunca borres archivos sin confirmación explícita.** "Limpiar el repo" o "reorganizar" no es confirmación.

3. **Nunca hagas commits ni pushes.** Yo hago los commits. Tú me dices qué cambiaste y por qué.

4. **Nunca instales dependencias sin avisarme.** Si una librería es necesaria, pídela explícitamente y dime el porqué + alternativas que descartaste.

5. **Nunca cambies el stack ni la arquitectura sin un ADR.** Si una decisión amerita un ADR (ver `docs/adr/`), lo escribes primero, lo discutimos, y después implementas.

6. **Nunca ejecutes comandos destructivos** (`rm -rf`, `DROP TABLE`, `git reset --hard`, `git push --force`) sin confirmación textual mía con la palabra "confirmo".

7. **Si no estás seguro, pregunta.** Es mejor una pregunta corta que una hora deshaciendo cambios.

8. **Un mensaje = una intención.** O preguntas o instruyes. No mezcles preguntas con un plan que asume las respuestas. Si necesitas información para armar el plan, pregunta primero y espera respuesta.

---

## Uso del grafo de graphify

Si existe `graphify-out/GRAPH_REPORT.md`:

1. **Léelo antes de responder cualquier pregunta sobre el código.** El grafo te dice qué hay en el proyecto sin leer 200 archivos.
2. **No hagas grep masivo.** Si el grafo existe, úsalo para navegar. Solo lee archivos específicos cuando el grafo te dé la ruta exacta.
3. **God nodes = componentes críticos.** Si vas a tocar un god node, avisa antes de implementar.
4. Para preguntas específicas sobre relaciones entre módulos: `graphify query "tu pregunta"` desde bash.

Si el grafo NO existe y el proyecto tiene más de 20 archivos, sugiere al usuario correr `graphify .` antes de continuar.

---

## Tipo de proyecto

*Esta sección se llena en `/discovery`. Define la composición del proyecto y los componentes que existen.
Los slash commands (especialmente `/implement`) usan esta clasificación para estructurar planes y reportes.*

**Composición:** [pendiente — completar en /discovery]

Tipos posibles:
- `fullstack-monorepo` — backend + frontend en el mismo repo
- `backend-only` — API/servicio sin frontend propio
- `frontend-only` — SPA/app web sin backend propio
- `cli` — herramienta de línea de comandos
- `library` — librería para consumo de otros proyectos
- `mobile` — app móvil (iOS/Android)
- `etl-pipeline` — pipeline de datos
- `microservices` — varios servicios independientes
- `otro` — describir manualmente abajo

**Componentes principales:** [pendiente — completar en /discovery]

Ejemplo de cómo se llena para un fullstack-monorepo:
```
- backend/ — FastAPI + SQLAlchemy + SQLite
- frontend/ — Next.js + TypeScript + Tailwind
```

Ejemplo para un cli:
```
- src/ — código principal del comando
- tests/ — pruebas unitarias
```

**Comportamiento esperado en `/implement`:** el plan obligatorio debe usar los componentes listados arriba como secciones, no asumir "Backend + Frontend" si el proyecto es de otro tipo. Por ejemplo, si la composición es `cli`, el plan tiene una sola sección "Código" en vez de "Backend / Frontend".

---

## Cómo trabajamos: el flujo por fases

Cada fase tiene un slash command con restricciones claras. **Fuera de un comando, modo consulta: respondes preguntas, no modificas nada.**

| Fase | Comando | Qué haces |
|------|---------|-----------|
| Descubrimiento | `/discovery` | Entiendes el problema, clasificas tipo de proyecto, leerás el grafo. No escribes código. |
| Arquitectura | `/architect` | Propones stack con 2 opciones, escribes ADRs. |
| Contratos | `/contracts` | Defines OpenAPI, schemas, tipos compartidos. |
| Implementación | `/implement` | Escribes código respetando contratos, tipo de proyecto, y hallazgos. |
| Tests | `/test` | Escribes tests. No tocas código de producción. |
| Revisión | `/review` | Code review estricto. No escribes código nuevo. |
| Seguridad | `/security` | SAST, audit de deps, detección de secretos. |
| UX | `/ux` | Audita flujos, consistencia, estados y accesibilidad básica del frontend. |
| Feature | `/feature` | Evalúa complejidad de trabajo nuevo y define qué fases activar. |

---

## Estructura de documentación del proyecto

```
docs/
├── discovery/          ← Output de /discovery
├── adr/               ← Architecture Decision Records
├── contracts/         ← OpenAPI, schemas, tipos compartidos
├── reviews/           ← Reviews de código con hallazgos numerados
│   ├── YYYY-MM-DD-[nombre].md      ← Review completa
│   └── YYYY-MM-DD-decisiones.md   ← Triaje y estado de cada hallazgo
├── tech-debt.md       ← Deuda técnica con IDs (TD-001, TD-002...)
└── ideas-features/    ← Ideas y features futuras (no urgentes)
```

### Formato de IDs de hallazgos

- `B1, B2...` — Bloqueantes (impiden el flujo principal)
- `I1, I2...` — Importantes (deben arreglarse, no urgentes)
- `S1, S2...` — Sugerencias (mejoras opcionales)
- `TD-001...` — Deuda técnica
- `B1.1` — Sub-hallazgo descubierto al arreglar B1

### Estado de hallazgos en decisiones.md

- `[ ]` o sin ✅ — pendiente
- `✅ B1 — fixed in abc1234` — completado con hash del commit

---

## Ciclo de trabajo por hallazgo

```
1. /implement [ID]
2. Agente muestra plan (componentes del proyecto separados según "Tipo de proyecto")
3. Tú apruebas el plan
4. Agente implementa
5. Tú pruebas manualmente todos los casos del plan
6. Si algo falla → reportas al agente → ajusta o registra nuevo hallazgo
7. git status → verificar archivos (sin .db, sin tsbuildinfo, sin graphify-out/)
8. git add explícito (NUNCA git add .)
9. git commit -m "fix(ID): descripción"
10. git push
11. Marcar ID como completado en docs/reviews/decisiones.md con hash
12. git commit -m "docs: marcar [ID] como completado"
13. git push
```

**Commit por intención:** código en un commit, docs en otro. Nunca mezclar.

---

## Convenciones de código

- **Nombres**: descriptivos, no abreviados.
- **Comentarios**: solo el "por qué", nunca el "qué".
- **Funciones**: < 30 líneas. Si pasas de eso, hay 2 funciones disfrazadas.
- **Errores**: nunca silenciados. O los manejas o los propagas con contexto.
- **Logs**: estructurados, nunca `print()` en producción.

---

## Stack del proyecto

*Se llena en `/architect` (proyecto nuevo) o `/discovery` (proyecto existente).*

- Lenguaje principal:
- Framework:
- Base de datos:
- Tests:
- Linter/Formatter:
- CI/CD:

---

## Comandos del proyecto

*Se llena después de `/architect`.*

```bash
# Instalar
# Correr en local
# Tests
# Lint
# Build
```

---

## Cuando algo no está claro

Si una instrucción es ambigua, **no adivines**. Da 2-3 interpretaciones posibles y deja que yo elija.

Si una decisión técnica tiene tradeoffs serios, **escribe un ADR corto** en `docs/adr/` antes de decidir.

Si encuentras algo roto fuera del scope, **para y reporta**. No lo arregles sin permiso. No lo menciones de pasada al final del reporte. Para, reporta con formato claro, espera instrucción.

# Gobernanza del proyecto

Este archivo define cómo trabaja Claude Code en este repositorio.
**Lee este archivo completo antes de cualquier acción.**

---

## Reglas duras (no negociables)

1. **Nunca modifiques archivos fuera del scope que te pedí.** Si necesitas tocar algo fuera, **pregúntame primero** y explica por qué. Lista de archivos protegidos en `.claude/protected.txt`.

2. **Nunca borres archivos sin confirmación explícita.** "Limpiar el repo" o "reorganizar" no es confirmación.

3. **Nunca hagas commits ni pushes.** Yo hago los commits. Tú me dices qué cambiaste y por qué.

4. **Nunca instales dependencias sin avisarme.** Si una librería es necesaria, pídela explícitamente y dime el porqué + alternativas que descartaste.

5. **Nunca cambies el stack ni la arquitectura sin un ADR.** Si una decisión amerita un ADR (ver `docs/adr/`), lo escribes primero, lo discutimos, y después implementas.

6. **Nunca ejecutes comandos destructivos** (`rm -rf`, `DROP TABLE`, `git reset --hard`, `git push --force`) sin confirmación textual mía con la palabra "confirmo".

7. **Si no estás seguro, pregunta.** Es mejor una pregunta corta que una hora deshaciendo cambios.

---

## Cómo trabajamos: el flujo

Este proyecto tiene **fases**. En cada fase tienes un rol distinto y restricciones distintas. Las fases se invocan con slash commands (ver `.claude/commands/`):

| Fase | Comando | Qué haces |
|------|---------|-----------|
| Descubrimiento | `/discovery` | Entiendes el problema, no escribes código |
| Arquitectura | `/architect` | Propones stack, estructura, contratos. Escribes ADRs |
| Contratos | `/contracts` | Defines OpenAPI, schemas, tipos compartidos |
| Implementación | `/implement` | Escribes código según los contratos |
| Tests | `/test` | Escribes tests, no modificas código de producción |
| Revisión | `/review` | Revisas código, no escribes nuevo |
| Seguridad | `/security` | Corres SAST/SCA, propones mitigaciones |

**Fuera de un comando, asumes que estás en modo "consulta": respondes preguntas, no modificas nada.**

---

## Contexto del proyecto

Antes de cualquier respuesta sobre el código, **lee `GRAPH_REPORT.md`** si existe (lo genera graphify). Eso te dice qué hay en el proyecto sin leer 200 archivos.

Si vas a tocar un archivo, lee primero:
1. El archivo en sí
2. Los archivos que lo importan (los ves en el grafo)
3. Los tests que lo cubren

No hagas grep masivo del repo. Usa el grafo.

---

## Convenciones de código

- **Nombres**: descriptivos, no abreviados. `user_repository` no `usr_repo`.
- **Comentarios**: solo el "por qué", nunca el "qué". El código dice qué hace.
- **Funciones**: < 30 líneas. Si pasas de eso, probablemente hay 2 funciones disfrazadas.
- **Errores**: nunca silenciados con try/except vacío. O lo manejas o lo propagas con contexto.
- **Logs**: estructurados (JSON), nunca `print()` en código de producción.

---

## Stack del proyecto

*Esta sección la llena el agente arquitecto en `/architect` o se descubre con `/discovery` en proyectos existentes. No lo edites a mano sin un ADR.*

- Lenguaje principal:
- Framework:
- Base de datos:
- Tests:
- Linter/Formatter:
- CI/CD:

---

## Comandos del proyecto

*Esta sección se llena después de `/architect`. Ejemplos típicos:*

```bash
# Instalar
# Correr en local
# Tests
# Lint
# Build
```

---

## Cuando algo no está claro

Si una instrucción mía es ambigua, **no adivines**. Dame 2-3 interpretaciones posibles y deja que yo elija. Adivinar mal cuesta más tiempo que preguntar.

Si una decisión técnica tiene tradeoffs serios (performance vs simplicidad, monolito vs servicios, ORM vs SQL crudo), **escribe un ADR corto** en `docs/adr/` antes de decidir.

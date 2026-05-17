# AI Workflow Template

Plantilla para desarrollar con Claude Code de forma disciplinada: cada fase del SDLC tiene su slash command, sus restricciones, y hooks que impiden que la IA se salga del scope.

**Esto es un punto de partida, no un framework cerrado.** Modifica los archivos en `.claude/` para adaptarlo a tu forma de trabajar.

---

## Cómo usar

### Para un proyecto nuevo

```bash
# 1. Crea repo desde la plantilla
gh repo create mi-proyecto --template tu-usuario/ai-workflow-template --private
cd mi-proyecto

# 2. Instala graphify (mapea el repo en un grafo para Claude)
uv tool install graphifyy && graphify install

# 3. Abre Claude Code en este folder
claude

# 4. Empieza el flujo
/discovery
```

### Para un proyecto existente

Usa el script `init.sh` (en el repo `ai-workflow-init`) que copia solo lo necesario sin pisar tu estructura:

```bash
cd mi-proyecto-existente
curl -fsSL https://raw.githubusercontent.com/tu-usuario/ai-workflow-init/main/init.sh | bash
```

Después:
```bash
graphify install && graphify .   # mapea lo que ya hay
claude
/discovery                        # entender qué tienes
```

---

## El flujo

```
/discovery → /architect → /contracts → /implement → /ux → /test → /review → /security
```

Cada fase tiene un comando, un rol, y restricciones claras. Fuera de un comando, Claude está en **modo consulta**: responde preguntas pero no modifica nada.

| Fase | Comando | ¿Qué hace? | Restricciones clave |
|------|---------|------------|---------------------|
| Descubrimiento | `/discovery` | Clasifica tipo de proyecto, entiende el problema, documenta estado actual | No escribe código, no propone stack |
| Arquitectura | `/architect` | Propone 2 opciones de stack, escribe ADRs | No escribe código de aplicación |
| Contratos | `/contracts` | Define OpenAPI, schemas, tipos compartidos | Solo interfaces, sin implementación |
| Implementación | `/implement <ID o feature>` | Escribe código respetando contratos y tipo de proyecto | No commitea, no instala deps sin avisar |
| Tests | `/test <target>` | Escribe tests | No toca código de producción |
| Revisión | `/review <target>` | Code review estricto con hallazgos numerados | No escribe código nuevo |
| Seguridad | `/security` | SAST, audit de deps, detección de secretos | Solo analiza y reporta |
| UX | `/ux` | Audita flujos, consistencia, estados y accesibilidad básica del frontend. |
---

## Sistema de hallazgos

Los hallazgos se numeran con IDs fijos para poder referenciarlos en commits, docs y conversaciones:

| Prefijo | Significado | Cuándo se arregla |
|---------|-------------|-------------------|
| `B1, B2...` | Bloqueante — impide el flujo principal | Antes de mergear |
| `I1, I2...` | Importante — debe arreglarse, no urgente | En el próximo ciclo |
| `S1, S2...` | Sugerencia — mejora opcional | Si hay tiempo |
| `TD-001...` | Deuda técnica — anotada, no urgente | Al inicio del siguiente sprint |
| `B1.1` | Sub-hallazgo descubierto al arreglar B1 | Junto con el padre |

Los hallazgos viven en `docs/reviews/`. Cada review tiene su archivo de decisiones con el estado de cada ID.

---

## Ciclo completo por hallazgo

```
1.  /implement [ID]
2.  Claude muestra plan estructurado por componentes del proyecto
3.  Tú apruebas el plan
4.  Claude implementa
5.  Tú pruebas manualmente todos los casos del plan
6.  Si algo falla → reportas → Claude ajusta o registra nuevo hallazgo
7.  git status → verificar que no haya archivos inesperados
8.  git add explícito (NUNCA git add .)
9.  git commit -m "fix(ID): descripción"       ← código
10. git push
11. Anotar hallazgos nuevos en docs/reviews/decisiones.md
12. git commit -m "docs: registrar [hallazgo]"  ← docs separado
13. Marcar ID como completado con hash del commit
14. git commit -m "docs: marcar [ID] como completado"
15. git push
```

**Un commit por intención:** código en un commit, docs en otro. Nunca mezclar.

---

## Hooks

Los hooks corren automáticamente antes y después de que Claude use herramientas. No requieren configuración manual.

| Hook | Cuándo corre | Qué hace |
|------|-------------|----------|
| `check-protected.sh` | Antes de escribir/editar cualquier archivo | Bloquea modificaciones a archivos listados en `.claude/protected.txt` |
| `check-bash.sh` | Antes de ejecutar bash | Bloquea comandos destructivos (`rm -rf`, `DROP TABLE`, `git push --force`, etc.) |
| `lint-on-save.sh` | Después de escribir/editar un archivo | Corre `ruff` en `.py` y `biome`/`prettier` en `.ts/.tsx/.js/.jsx` |
| `session-summary.sh` | Al terminar la sesión | Muestra resumen de archivos modificados y recuerda que los commits son del usuario |

Los archivos que Claude nunca puede tocar se listan en `.claude/protected.txt`:

```
.env, .env.*, *.pem, *.key, secrets/**, .git/**, .github/workflows/**,
.claude/protected.txt, CLAUDE.md, docs/adr/**, docs/contracts/**, LICENSE
```

---

## Estructura

```
mi-proyecto/
├── CLAUDE.md                          ← Reglas duras, convenciones, tipo de proyecto
├── .claude/
│   ├── settings.json                  ← Configuración de hooks (PreToolUse / PostToolUse / Stop)
│   ├── protected.txt                  ← Archivos que Claude no puede modificar
│   ├── commands/                      ← Slash commands (uno por fase del SDLC)
│   │   ├── discovery.md
│   │   ├── architect.md
│   │   ├── implement.md
│   │   └── review.md
│   ├── hooks/                         ← Scripts de pre/post tool use
│   │   ├── check-protected.sh
│   │   ├── check-bash.sh
│   │   ├── lint-on-save.sh
│   │   └── session-summary.sh
│   └── agents/                        ← Vacío, para subagentes futuros
├── docs/
│   ├── discovery/                     ← Output de /discovery
│   ├── adr/                           ← Architecture Decision Records (formato Nygard)
│   ├── contracts/                     ← OpenAPI, schemas, tipos compartidos
│   ├── reviews/                       ← Reviews con hallazgos numerados
│   │   ├── YYYY-MM-DD-[nombre].md     ← Review completa
│   │   └── YYYY-MM-DD-decisiones.md  ← Triaje y estado de cada hallazgo
│   ├── tech-debt.md                   ← Deuda técnica con IDs (TD-001, TD-002...)
│   └── ideas-features/               ← Features futuras no urgentes
├── graphify-out/                      ← Grafo del repo (no versionar, excepto .gitkeep)
└── src/                               ← Tu código (lo crea /architect)
```

---

## Convenciones de código

Estas aplican a todo código que Claude escriba en este repo:

- **Nombres:** descriptivos, no abreviados.
- **Comentarios:** solo el "por qué", nunca el "qué".
- **Funciones:** menos de 30 líneas. Si pasas de eso, hay dos funciones disfrazadas.
- **Errores:** nunca silenciados. O los manejas o los propagas con contexto.
- **Logs:** estructurados, nunca `print()` en producción.

---

## Reglas duras (resumen)

El detalle completo está en `CLAUDE.md`. En resumen, Claude nunca puede:

- Modificar archivos fuera del scope pedido sin preguntar primero
- Borrar archivos sin confirmación explícita
- Hacer commits o pushes
- Instalar dependencias sin avisar y justificar
- Cambiar stack o arquitectura sin un ADR previo
- Ejecutar comandos destructivos sin que el usuario escriba "confirmo"
- Mezclar una pregunta con un plan que ya asume la respuesta

---

## Graphify

[graphify](https://github.com/tu-usuario/graphifyy) construye un grafo del repositorio que Claude usa para navegar sin hacer búsquedas masivas de archivos. Reduce consumo de tokens, detecta god nodes (componentes críticos por número de dependencias), y permite que Claude clasifique el tipo de proyecto automáticamente en `/discovery`.

```bash
# Instalar
uv tool install graphifyy
graphify install

# Construir el grafo (correr desde la raíz del proyecto)
graphify .

# El reporte queda en:
graphify-out/GRAPH_REPORT.md
```

El directorio `graphify-out/` está en `.gitignore` (excepto el `.gitkeep`). Cada desarrollador regenera el grafo localmente.

---

## Lo que esta plantilla NO incluye (a propósito)

- **Multi-agente real (LangGraph/CrewAI):** complejo, caro en tokens, difícil de debuggear. Si lo necesitas, agrégalo cuando el proyecto lo justifique.
- **CI/CD prefabricado:** depende del stack. Se define en `/architect`.
- **Docker compose default:** se agrega cuando la arquitectura lo justifique.
- **Modelo local (Ollama):** un modelo de 7B no hace arquitectura seria.

---

## Cuándo extender la plantilla

| Dolor recurrente | Solución |
|-----------------|----------|
| Claude toca archivos que no debería | Agregar entradas a `.claude/protected.txt` |
| Claude pierde contexto entre sesiones | MCP server con graphify + memory |
| Quieres roles con comportamiento distinto | Subagentes en `.claude/agents/` |
| Tests no corren automáticamente al cambiar código | Extender el hook `PostToolUse` en `settings.json` |
| Quieres las mismas validaciones en CI | Mover la lógica de hooks a GitHub Actions workflows |

---

## Licencia

MIT

# AI Workflow Template

Plantilla mínima viable para desarrollar con Claude Code de forma disciplinada: cada fase del SDLC tiene su slash command, sus restricciones, y la IA no se sale del scope.

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
/discovery   →  /architect   →  /contracts   →  /implement   →  /test   →  /review   →  /security
```

Cada fase tiene un comando, un rol, y restricciones claras. Lee `CLAUDE.md` y los archivos en `.claude/commands/` para entender exactamente qué hace cada uno.

| Fase | Comando | ¿Qué hace? |
|------|---------|-----------|
| Descubrimiento | `/discovery` | Entender el problema (proyecto nuevo) o el estado actual (existente) |
| Arquitectura | `/architect` | Proponer stack y escribir ADRs |
| Contratos | `/contracts` | Definir OpenAPI, schemas, tipos compartidos |
| Implementación | `/implement <feature>` | Escribir código respetando contratos |
| Tests | `/test <target>` | Escribir tests sin tocar código de prod |
| Revisión | `/review <target>` | Code review estricto sin escribir código |
| Seguridad | `/security` | SAST, audit de deps, detección de secretos |

---

## Lo que esta plantilla NO incluye (a propósito)

- **Multi-agente real (LangGraph/CrewAI):** complejo, caro en tokens, difícil de debuggear. Si lo necesitas después, súbelo de nivel.
- **CI/CD prefabricado:** depende del stack. Lo armamos en `/architect` cuando se sepa qué stack es.
- **Docker compose default:** se agrega cuando arquitectura lo justifique.
- **Modelo local (Ollama):** un modelo de 7B no hace arquitectura seria. Usa Claude/GPT.

---

## Estructura

```
mi-proyecto/
├── CLAUDE.md                    ← Reglas duras para Claude Code
├── .claude/
│   ├── settings.json            ← Hooks
│   ├── protected.txt            ← Archivos que Claude no puede tocar
│   ├── commands/                ← Slash commands (uno por fase)
│   ├── hooks/                   ← Hooks de pre/post tool use
│   └── agents/                  ← (Vacío, para subagentes futuros)
├── docs/
│   ├── discovery/               ← Output de /discovery
│   ├── adr/                     ← Architecture Decision Records
│   └── contracts/               ← OpenAPI, schemas
└── src/                         ← Tu código (lo crea /architect)
```

---

## Cuándo subir de nivel

Si después de 2-3 semanas notas alguno de estos dolores, abre un chat nuevo con Claude y pide el módulo correspondiente (ver tabla en la conversación original):

- "Claude se mete en archivos que no debería" → reglas adicionales en hooks
- "Cada sesión Claude pierde contexto del proyecto" → MCP server con graphify + memory
- "Quiero que diferentes 'roles' tengan personalidades distintas" → subagentes en `.claude/agents/`
- "Los tests no se corren automáticamente al cambiar código" → hook `PostToolUse` extendido
- "Quiero que el CI corra estas mismas validaciones" → workflows de GitHub Actions

---

## Licencia

MIT (o lo que prefieras)

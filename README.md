# AI Workflow Template

Plantilla para desarrollar aplicaciones con Claude Code de forma disciplinada: cada fase del SDLC tiene su slash command, sus restricciones, y hooks que impiden que la IA se salga del scope.

Incluye estrategia de Git profesional (branches, hooks de calidad, commits convencionales), gestión de cambios post-deploy, y contratos entre componentes que `/implement` no puede ignorar.

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

# 4. Configura Git primero
/git-setup

# 5. Empieza el flujo
/discovery
```

### Para un proyecto existente

```bash
cd mi-proyecto-existente
# Copia .claude/, git-hooks/, CLAUDE.md y README.md desde la plantilla

graphify install && graphify .   # mapea lo que ya hay
claude
/git-setup                        # configura branches y hooks
/discovery                        # entender qué tienes
```

---

## El flujo completo

```
/git-setup          Configura main/develop, instala hooks de Git. Solo al inicio.
     ↓
/discovery          Clasifica el proyecto, entiende el problema, fija el norte.
     ↓
/architect          Propone 2 opciones de stack, escribe ADRs.
     ↓
/contracts          Define API, schemas de DB, tipos compartidos, env vars.
     ↓
/implement          Escribe código respetando contratos y tipo de proyecto.
     ↓
/test               Suite de tests: unitarios, integración, API y E2E.
/review             Code review estricto con hallazgos numerados.
/security           Audita auth, inyecciones, deps y secretos.
/ux                 Audita flujos y consistencia del frontend (si aplica).
     ↓
/deploy             Checklist pre-producción: tests, migraciones, env vars, monitoreo.
     ↓
     ⟲ /change      Modificaciones post-deploy. Clasifica el cambio, identifica
                    contratos afectados, re-corre solo las fases mínimas necesarias.
```

Para trabajo nuevo o cambios significativos, `/feature` evalúa la complejidad y define qué fases del flujo activar.

Cada fase tiene un comando, un rol, y restricciones claras. Fuera de un comando, Claude está en **modo consulta**: responde preguntas pero no modifica nada.

| Fase | Comando | Restricciones clave |
|------|---------|---------------------|
| Init Git | `/git-setup` | Solo una vez al inicio. No toca código. |
| Descubrimiento | `/discovery` | No escribe código, no propone stack. |
| Arquitectura | `/architect` | No escribe código de aplicación. |
| Contratos | `/contracts` | Solo interfaces y especificaciones, sin implementación. |
| Implementación | `/implement <ID o feature>` | No commitea, no instala deps sin avisar. Muestra plan antes de tocar código. |
| Tests | `/test <target>` | No toca código de producción. |
| Revisión | `/review <target>` | Solo analiza y reporta, no reescribe. |
| Seguridad | `/security` | Solo analiza y reporta, no reescribe. |
| UX | `/ux <flujo>` | Solo audita flujos de frontend, no reescribe. |
| Feature | `/feature <descripción>` | Evalúa antes de actuar. Ancla al norte del proyecto. |
| Pre-producción | `/deploy` | Solo verifica y documenta. No modifica código. |
| Cambio post-deploy | `/change <descripción>` | Proporcional al tamaño del cambio. |

---

## Estrategia de Git

```
main              ← producción, siempre deployable, tag semver en cada release
  └── develop     ← integración continua
        ├── feature/[slug]  ← una branch por feature o cambio significativo
        ├── fix/[slug]      ← corrección de bug no urgente
        └── hotfix/[slug]   ← arreglo urgente, se crea desde main directamente
```

### Commits convencionales

El hook `commit-msg` valida el formato automáticamente:

```
feat(usuarios): agregar endpoint de registro con validación de email
fix(B3): corregir error de autenticación en refresh token expirado
docs: contratos de API actualizados
chore: workflow inicializado
refactor(auth): extraer lógica de JWT a módulo propio
perf(queries): agregar índice en tabla de eventos
```

### Tags semver

```
v0.0.1      ← /git-setup (workflow inicializado)
v1.0.0      ← /deploy (primer deploy a producción)
v1.1.0      ← nueva funcionalidad significativa
v1.1.1      ← bugfix o ajuste menor
```

### Ciclo completo: feature → develop → main

```bash
# 1. Crear branch desde develop
git checkout develop && git checkout -b feature/[slug]

# 2. Trabajar... commits convencionales...

# 3. Mergear a develop
git checkout develop
git merge feature/[slug] --no-ff -m "feat([scope]): descripción"
git branch -d feature/[slug] && git push origin develop

# 4. Release a producción
git checkout main
git merge develop --no-ff -m "release: descripción"
git tag -a v[X.Y.Z] -m "release: descripción"
git push origin main --follow-tags

# 5. Sincronizar develop
git checkout develop && git merge main && git push origin develop
```

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
0.  Estar en branch correcta: git checkout develop && git checkout -b fix/[slug]
1.  /implement [ID]
2.  Claude muestra plan estructurado por componentes del proyecto
3.  Tú apruebas el plan
4.  Claude implementa
5.  Tú pruebas manualmente todos los casos del plan
6.  Si algo falla → reportas → Claude ajusta o registra nuevo hallazgo
7.  git status → verificar que no haya archivos inesperados
8.  git add explícito (NUNCA git add .)
9.  git commit -m "fix(ID): descripción"           ← código
10. git commit -m "docs: marcar [ID] como completado"  ← docs separado
11. git checkout develop && git merge fix/[slug] --no-ff
12. git branch -d fix/[slug] && git push origin develop
```

**Un commit por intención:** código en un commit, docs en otro. Nunca mezclar.

---

## Cambios post-deploy

Cuando la aplicación ya está en producción, `/change` es el punto de entrada para cualquier modificación.

**Principio: proporcionalidad.** Un bugfix puntual no re-corre `/security` completo. Un nuevo endpoint no re-corre `/architect`. `/change` clasifica el cambio, identifica qué contratos toca, y re-corre solo lo necesario.

### Clasificación de cambios

| Categoría | Ejemplo |
|-----------|---------|
| Configuración | Cambiar env var, feature flag, timeout |
| Funcionalidad | Nuevo endpoint, nueva lógica de negocio |
| Schema/Migración | Agregar columna, nueva tabla, cambiar tipo |
| Bug | Algo que debería funcionar y no funciona |
| Arquitectura | Nuevo servicio, cambio de patrón estructural |

### Branch según el cambio

| Situación | Branch |
|-----------|--------|
| Bug urgente en producción | `hotfix/[slug]` desde `main` |
| Bug no urgente / config / ajuste | `fix/[slug]` desde `develop` |
| Funcionalidad nueva / schema | `feature/[slug]` desde `develop` |

Cada cambio queda registrado en `docs/changes/YYYY-MM-DD-[slug].md`.

---

## Hooks

### Claude Code hooks (`.claude/hooks/`) — automáticos, sin configuración manual

| Hook | Cuándo corre | Qué hace |
|------|-------------|----------|
| `check-protected.sh` | Antes de editar cualquier archivo | Bloquea modificaciones a archivos en `.claude/protected.txt` |
| `check-branch.sh` | Antes de editar cualquier archivo | Advierte si se está trabajando directamente en `main` |
| `check-bash.sh` | Antes de ejecutar bash | Bloquea comandos destructivos (`rm -rf`, `DROP TABLE`, `git push --force`, etc.) |
| `lint-on-save.sh` | Después de editar un archivo | Corre `ruff` en `.py` y `biome`/`prettier` en `.ts/.tsx/.js/.jsx` |
| `session-summary.sh` | Al terminar la sesión | Muestra resumen de archivos modificados y recuerda que los commits son del usuario |

### Git hooks (`git-hooks/`) — instalados por `/git-setup`

| Hook | Qué hace |
|------|----------|
| `pre-commit` | Bloquea archivos prohibidos (`.env`, `*.db`), lint JS/TS, type-check TypeScript, lint Python con ruff |
| `commit-msg` | Valida formato convencional: `tipo(scope): descripción`. Rechaza el commit si no cumple. |
| `pre-push` | Corre tests (npm test / pytest según stack detectado), advierte push directo a main |

Los archivos que Claude nunca puede tocar sin autorización explícita se listan en `.claude/protected.txt`:

```
.env, .env.*, *.pem, *.key, secrets/**, .git/**, .github/workflows/**,
.claude/protected.txt, CLAUDE.md, docs/adr/**, docs/contracts/**, LICENSE
```

---

## Estructura

```
mi-proyecto/
├── CLAUDE.md                          ← Reglas, norte del proyecto, estrategia de Git
├── .claude/
│   ├── settings.json                  ← Hooks de Claude Code (PreToolUse / PostToolUse / Stop)
│   ├── protected.txt                  ← Archivos que Claude no puede modificar
│   ├── commands/                      ← Slash commands (uno por fase del SDLC)
│   │   ├── git-setup.md              ← /git-setup
│   │   ├── discovery.md              ← /discovery
│   │   ├── architect.md              ← /architect
│   │   ├── contracts.md              ← /contracts
│   │   ├── implement.md              ← /implement
│   │   ├── test.md                   ← /test
│   │   ├── review.md                 ← /review
│   │   ├── security.md               ← /security
│   │   ├── ux.md                     ← /ux
│   │   ├── feature.md                ← /feature
│   │   ├── deploy.md                 ← /deploy
│   │   └── change.md                 ← /change
│   └── hooks/                         ← Scripts de Claude Code
│       ├── check-protected.sh
│       ├── check-branch.sh
│       ├── check-bash.sh
│       ├── lint-on-save.sh
│       └── session-summary.sh
├── git-hooks/                         ← Hooks de Git (versionados, instalados por /git-setup)
│   ├── pre-commit
│   ├── commit-msg
│   └── pre-push
├── docs/
│   ├── discovery/                     ← Output de /discovery
│   ├── adr/                           ← Architecture Decision Records (formato Nygard)
│   ├── contracts/                     ← API, schemas, tipos, env vars
│   ├── features/                      ← Tracking de features activas
│   │   └── YYYY-MM-DD-[slug].md
│   ├── reviews/                       ← Hallazgos de /review, /security, /ux
│   │   ├── YYYY-MM-DD-[nombre].md
│   │   └── YYYY-MM-DD-decisiones.md
│   ├── changes/                       ← Registro de /change (post-deploy)
│   │   └── YYYY-MM-DD-[slug].md
│   ├── tech-debt.md                   ← Deuda técnica con IDs (TD-001, TD-002...)
│   └── ideas-features/               ← Ideas futuras sin scope definido
├── graphify-out/                      ← Grafo del repo (no versionar, excepto .gitkeep)
└── src/                               ← Tu código (lo crea /architect)
```

---

## Convenciones de código

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
- Trabajar directamente en `main`
- Commitear con mensajes fuera del formato convencional
- Redefinir el norte del proyecto silenciosamente

---

## Graphify

[graphify](https://github.com/tu-usuario/graphifyy) construye un grafo del repositorio que Claude usa para navegar sin hacer búsquedas masivas. Reduce consumo de tokens, detecta god nodes (componentes críticos), y permite clasificar el tipo de proyecto automáticamente en `/discovery`.

```bash
# Instalar
uv tool install graphifyy
graphify install

# Construir el grafo (desde la raíz del proyecto)
graphify .

# El reporte queda en:
graphify-out/GRAPH_REPORT.md
```

El directorio `graphify-out/` está en `.gitignore` (excepto el `.gitkeep`). Cada desarrollador regenera el grafo localmente.

---

## Lo que esta plantilla NO incluye (a propósito)

- **Rama `staging`:** se puede agregar si el equipo lo necesita, pero agrega complejidad. La mayoría de proyectos funcionan bien con main/develop.
- **CI/CD prefabricado:** depende del stack y la infraestructura. Se define en `/architect` y se puede automatizar con los mismos git hooks.
- **Multi-agente real (LangGraph/CrewAI):** complejo, caro en tokens, difícil de debuggear. Agregar cuando el proyecto lo justifique.
- **Docker compose default:** se agrega cuando la arquitectura lo justifique.

---

## Mantener el workflow actualizado

Cuando el template evoluciona (nuevos comandos, mejoras a hooks, nuevas reglas), los proyectos existentes no se actualizan solos. Para eso está `sync-workflow.sh`.

```bash
# Ver qué cambiaría sin escribir nada
bash sync-workflow.sh --dry-run

# Actualizar el workflow
bash sync-workflow.sh
```

**Qué sincroniza:**
- `.claude/commands/` — todos los slash commands
- `.claude/hooks/` — hooks de Claude Code
- `.claude/settings.json` — configuración de hooks
- `.claude/protected.txt` — lista de archivos protegidos
- `git-hooks/` — pre-commit, commit-msg, pre-push

**Qué nunca toca:**
- `CLAUDE.md` — tiene el norte del proyecto, stack y configuración específica
- `README.md`, `docs/`, ni ningún código del proyecto

Si los git-hooks cambiaron, el script avisa. Reinstálalos con `/git-setup`.

Para repos privados o si encuentras rate limiting de GitHub API, exporta un token:
```bash
export GITHUB_TOKEN=ghp_tu_token
bash sync-workflow.sh
```

---

## Cuándo extender la plantilla

| Dolor recurrente | Solución |
|-----------------|----------|
| Claude toca archivos que no debería | Agregar entradas a `.claude/protected.txt` |
| Claude pierde contexto entre sesiones | MCP server con graphify + memory |
| Quieres tests corriendo en CI también | Copiar la lógica de `git-hooks/pre-push` a un GitHub Actions workflow |
| Necesitas rama `staging` | Agregar `staging` entre `develop` y `main`, ajustar `/git-setup` |
| Quieres roles con comportamiento distinto | Subagentes en `.claude/agents/` |

---

## Licencia

MIT

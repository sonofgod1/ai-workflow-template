# AI Workflow Template

Plantilla para desarrollar aplicaciones con **Claude Code o Cursor** de forma disciplinada: cada fase del SDLC tiene su comando, sus restricciones, y hooks que impiden que la IA se salga del scope.

El mismo flujo funciona en los dos editores. Lo que cambia es cuánto se puede hacer cumplir con código — ver [Claude Code y Cursor](#claude-code-y-cursor).

Incluye estrategia de Git profesional (branches, hooks de calidad, commits convencionales), gestión de cambios post-deploy, y contratos entre componentes que `/implement` no puede ignorar.

**Esto es un punto de partida, no un framework cerrado.** Modifica los archivos en `.claude/` o `.cursor/` para adaptarlo a tu forma de trabajar.

---

## Cómo usar

### Para un proyecto nuevo

```bash
# 1. Crea repo desde la plantilla
gh repo create mi-proyecto --template tu-usuario/ai-workflow-template --private
cd mi-proyecto

# 2. Instala graphify (mapea el repo en un grafo para Claude)
uv tool install graphifyy && graphify install

# 3. Abre tu editor en este folder
claude          # Claude Code
# o simplemente abre la carpeta en Cursor

# 4. Configura Git primero
/git-setup      # en Cursor: @git-setup

# 5. Empieza el flujo
/discovery      # en Cursor: @discovery
```

La plantilla trae los dos juegos de reglas (`.claude/` y `.cursor/`). Si solo usas uno, puedes borrar el otro — o dejarlos, no estorban.

### Para un proyecto existente

```bash
cd mi-proyecto-existente
# Copia git-hooks/ y, según tu editor:
#   Claude Code → .claude/ + CLAUDE.md
#   Cursor      → .cursor/
#   los dos     → todo lo anterior

graphify install && graphify .   # mapea lo que ya hay
claude                            # o abre la carpeta en Cursor
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

Cada fase tiene un comando, un rol, y restricciones claras. Fuera de un comando, el agente está en **modo consulta**: responde preguntas pero no modifica nada.

En Cursor los mismos comandos se invocan con `@`: `@discovery`, `@implement`, `@review`.

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

## Claude Code y Cursor

Los 12 comandos son **idénticos palabra por palabra** en los dos editores. Lo que cambia es cómo se
invocan y cuánto se puede hacer cumplir con código.

| | Claude Code | Cursor |
|---|---|---|
| Invocar una fase | `/implement` | `@implement` |
| Dónde viven las fases | `.claude/commands/*.md` | `.cursor/rules/*.mdc` |
| Norte y reglas duras | `CLAUDE.md` (se carga solo) | `.cursor/rules/00-gobernanza.mdc` (`alwaysApply: true`) |
| Formato convencional de commits | ✅ `commit-msg` | ✅ el mismo hook |
| Bloqueo de `.env`, `*.db`, etc. al commitear | ✅ `pre-commit` | ✅ |
| Lint y type-check antes del commit | ✅ `pre-commit` | ✅ |
| Tests antes del push | ✅ `pre-push` | ✅ |
| **Bloqueo de archivos protegidos** | ✅ `check-protected.sh` | ❌ no existe |
| **Bloqueo de comandos destructivos** | ✅ `check-bash.sh` | ❌ no existe |
| Lint al guardar | ✅ `lint-on-save.sh` | ❌ (usa el del editor) |
| Aviso al trabajar en `main` | ✅ `check-branch.sh` | ❌ |
| Resumen al terminar la sesión | ✅ `session-summary.sh` | ❌ |

### Qué significa en la práctica

**Los git hooks son de Git, no del editor.** `commit-msg`, `pre-commit` y `pre-push` corren igual en
los dos: la validación de commits, el bloqueo de archivos prohibidos, el lint y los tests son
exactamente la misma barrera. Esa mitad de la gobernanza es idéntica.

**Lo que Cursor no tiene es un equivalente de `PreToolUse`**: no hay manera de que un script
intercepte una escritura o un comando *antes* de que ocurra. Por eso la protección de archivos y el
bloqueo de `rm -rf` pasan de "no puedes" a "no debes". La regla `00-gobernanza` se lo dice al agente
de forma explícita en cada request, y lista los archivos protegidos en línea para que no dependa de
leer un archivo aparte — pero es persuasión, no un portón.

**En Cursor, mira el `git status` antes de commitear con más atención de la que harías en Claude Code.**

Dicho eso, la barrera que de verdad cuenta es la misma para los dos: el CI y la branch protection
corren en el servidor. Ver [Capas de protección](#capas-de-protección).

### La regla `00-gobernanza`

Es el equivalente de `CLAUDE.md`: norte del proyecto, las 11 reglas duras, tipo de proyecto, tabla de
fases, estrategia de Git y convenciones. Se aplica siempre.

Es **tuya, no de la plantilla**: `@discovery` le escribe el norte y el tipo de proyecto, `@architect`
el stack. Igual que `CLAUDE.md`, `sync-workflow.sh` nunca la sobrescribe si ya existe.

### Las reglas de Cursor se generan, no se editan

`.claude/commands/*.md` y `CLAUDE.md` son la **única fuente de verdad**. Las reglas de Cursor son un
derivado que produce `generate-cursor-rules.sh`:

```bash
bash generate-cursor-rules.sh            # regenera .cursor/rules/
bash generate-cursor-rules.sh --check    # falla si están desactualizadas (útil en CI)
bash generate-cursor-rules.sh --force    # regenera también 00-gobernanza.mdc
```

El script traduce lo que no existe en Cursor: los slash commands pasan a `@comando`, `$ARGUMENTS`
se convierte en una instrucción que usa el `argument-hint` de la fuente, y `CLAUDE.md` pasa a
`00-gobernanza`. Al terminar **verifica el resultado**: si queda una referencia a `.claude/`, a un
slash command o a `$ARGUMENTS`, falla y te dice el archivo y la línea en vez de publicar una regla
rota.

`00-gobernanza.mdc` se preserva si ya tiene un norte definido — regenerarlo desde el `CLAUDE.md` de
la plantilla lo borraría. Usa `--force` solo si sabes lo que haces.

**Si editas una regla `.mdc` a mano, el siguiente `generate` la pisa.** Edita la fuente en
`.claude/commands/` y regenera. Así es como `implement.mdc` terminó una vez con el 13% de su
contenido: se editó por separado y nadie notó la deriva.

---

## Hooks

### Claude Code hooks (`.claude/hooks/`) — solo Claude Code

Son los que Cursor no puede replicar. Automáticos, sin configuración manual.

| Hook | Cuándo corre | Qué hace |
|------|-------------|----------|
| `check-protected.sh` | Antes de editar cualquier archivo | Bloquea modificaciones a archivos en `.claude/protected.txt` |
| `check-branch.sh` | Antes de editar cualquier archivo | Advierte si se está trabajando directamente en `main` |
| `check-bash.sh` | Antes de ejecutar bash | Bloquea comandos destructivos (`rm -rf`, `DROP TABLE`, `git push --force`, etc.) |
| `lint-on-save.sh` | Después de editar un archivo | Corre `ruff` en `.py` y `biome`/`prettier` en `.ts/.tsx/.js/.jsx` |
| `session-summary.sh` | Al terminar la sesión | Muestra resumen de archivos modificados y recuerda que los commits son del usuario |

### Git hooks (`git-hooks/`) — los dos editores

Instalados por `/git-setup` (o `@git-setup`). Son hooks de Git, así que funcionan igual sin importar con qué edites.

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
├── .github/
│   ├── workflows/ci.yml               ← La barrera del servidor (no se salta)
│   └── CODEOWNERS                     ← Quién aprueba qué (rellenar @TU-USUARIO)
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
├── .cursor/
│   └── rules/                         ← Las mismas fases para Cursor
│       ├── 00-gobernanza.mdc         ← equivalente de CLAUDE.md (alwaysApply)
│       ├── discovery.mdc             ← @discovery
│       ├── implement.mdc             ← @implement
│       └── ...                        ← una por fase, igual que en .claude/commands/
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

## Capas de protección

La regla de fondo: **lo que de verdad protege no vive en el editor.** Un equipo con cinco personas
usando cinco editores distintos no puede depender de que cada una tenga el hook instalado.

| Capa | Dónde corre | ¿Se puede saltar? | Qué cubre |
|---|---|---|---|
| Reglas y comandos | editor | sí, trivialmente | la intención del agente |
| Hooks de Claude Code | local, solo Claude Code | sí | archivos protegidos, comandos destructivos |
| Git hooks | local, cualquier editor | sí: `--no-verify` | commits, archivos prohibidos, lint, tests |
| **CI** | servidor | **no** | lo mismo, más secretos, sobre el PR completo |
| **CODEOWNERS** | servidor | **no** | quién puede cambiar qué |
| **Branch protection** | servidor | **no** (salvo admin) | qué llega a `main` |

Las tres primeras dan feedback rápido; las tres últimas son las que garantizan algo. Por eso la
diferencia entre Claude Code y Cursor importa menos de lo que parece: la capa que manda es la misma
para los dos.

### CI (`.github/workflows/ci.yml`)

Corre en cada PR a `main` y `develop`, y en cada push a esas ramas:

| Job | Qué hace |
|---|---|
| `archivos-prohibidos` | Busca `.env`, `*.db`, `*.pem`, `node_modules/` y demás versionados en el repo |
| `commits-convencionales` | Valida el asunto de **todos** los commits del PR, con el mismo patrón que `commit-msg` |
| `secretos` | gitleaks sobre el historial completo |
| `javascript` | `npm ci`, lint (biome o eslint), `tsc --noEmit`, tests — solo si hay `package.json` |
| `python` | ruff y pytest — solo si hay `pyproject.toml` o `setup.py` |

Los jobs de stack se activan solos según lo que encuentren en el repo, así que el workflow sirve
igual para un CLI en Python que para un monorepo fullstack.

`commits-convencionales` es el que cierra el agujero: `git commit --no-verify` esquiva el hook local,
pero el PR no se puede mergear con un commit mal formado.

### CODEOWNERS (`.github/CODEOWNERS`)

El equivalente de `.claude/protected.txt`, pero del lado del servidor. Los ADRs, los contratos, la
gobernanza y el propio CI requieren tu aprobación para cambiar — venga el cambio de un agente, de un
compañero o de ti mismo desde otra rama.

**Hay que reemplazar `@TU-USUARIO` por tu usuario real de GitHub.** Sin eso GitHub ignora el archivo
entero. `/git-setup` lo pide y da el comando.

### Branch protection

`/git-setup` imprime los comandos de `gh api` para exigir PR, CI en verde y review de code owners en
`main` y `develop`. Es lo que hace que "`main` siempre es deployable" pase de intención a garantía.

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
- **Deploy automatizado:** el CI verifica, pero no despliega. Dónde y cómo se despliega depende de la infraestructura; se define en `/architect`.
- **Multi-agente real (LangGraph/CrewAI):** complejo, caro en tokens, difícil de debuggear. Agregar cuando el proyecto lo justifique.
- **Docker compose default:** se agrega cuando la arquitectura lo justifique.

---

## Mantener el workflow actualizado

Cuando el template evoluciona (nuevos comandos, mejoras a hooks, nuevas reglas), los proyectos existentes no se actualizan solos. Para eso está `sync-workflow.sh`.

```bash
# Ver qué cambiaría sin escribir nada
bash sync-workflow.sh --dry-run

# Actualizar el workflow (por defecto: Claude Code)
bash sync-workflow.sh

# Elegir editor explícitamente
bash sync-workflow.sh --editor cursor
bash sync-workflow.sh --editor all
```

**`--editor`** acepta `claude` (por defecto), `cursor` o `all`. Los `git-hooks/` se sincronizan
siempre, con cualquier valor, porque no dependen del editor.

**Qué sincroniza:**

| `--editor` | Rutas |
|---|---|
| *(siempre)* | `git-hooks/` — pre-commit, commit-msg, pre-push<br>`.github/` — CI y CODEOWNERS |
| `claude` | `.claude/commands/`, `.claude/hooks/`, `.claude/settings.json`, `.claude/protected.txt` |
| `cursor` | `.cursor/rules/` |
| `all` | todo lo anterior |

**Qué nunca toca:**
- `CLAUDE.md` — tiene el norte del proyecto, stack y configuración específica
- `.cursor/rules/00-gobernanza.mdc` — lo mismo, para Cursor. Si ya existe se preserva y el script
  lo reporta; solo se descarga en una instalación nueva, con sus `[pendiente]` sin llenar
- `.github/CODEOWNERS` — lleva tu usuario real de GitHub; se preserva igual que el anterior
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
| Claude toca archivos que no debería | Agregar entradas a `.claude/protected.txt` (en Cursor: a la lista de la regla 1 de `00-gobernanza`) |
| Claude pierde contexto entre sesiones | MCP server con graphify + memory |
| Quieres tests corriendo en CI también | Copiar la lógica de `git-hooks/pre-push` a un GitHub Actions workflow |
| Necesitas rama `staging` | Agregar `staging` entre `develop` y `main`, ajustar `/git-setup` |
| Quieres roles con comportamiento distinto | Subagentes en `.claude/agents/` |

---

## Licencia

MIT

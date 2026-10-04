# SPEC

## §G GOAL
Andamiaje para construir sistemas digitales con agentes: una spec viva manda,
el código se verifica contra ella, y el proceso de producción es opt-in.

## §M MODE
spec

## §C CONSTRAINTS
- Constitución always-on ≤ ~200 líneas. El SDLC largo vive en `docs/workflow.md`, no en cada turno.
- SPEC.md es la única spec de producto. Planes, contratos, ADRs y findings son soporte. Si discrepan, gana SPEC.md hasta enmendarla.
- Tres modos: `explore` (bosquejar), `spec` (loop SDD), `production` (review/security/migrate/ship).
- Fuera de un comando el agente PUEDE escribir código si el usuario lo pidió. No hay modo consulta que prohíba construir.
- GitHub Flow por defecto: `main` + `feature/*` + PR. `develop` es opt-in (`BASE_POR_DEFECTO`).
- Graphify es opcional, nunca bloquea el primer día.
- `verify.sh` es la evidencia. Nada se declara terminado sin pegar su salida.
- No commits ni pushes del agente salvo `.workflow/delivery.conf` con `MODO_ENTREGA=pr`.
- El merge nunca es del agente.
- En Cursor no hay PreToolUse: las reglas duras de escritura se respetan como si el hook existiera.
- `.workflow/` se verifica aquí; los proyectos consumidores lo excluyen de su linter.
- §I y §V live = comportamiento actual. Lo que aún no es verdad va a §D hasta el fold.
- El que construye no certifica. El que certifica no escribe. El que no es un modelo es `verify.sh`.

## §I INTERFACES
- cmd: `/spec` `@spec` → muta SPEC.md (new / amend / bug / distill). Cambio no-actual → §D, no reescribe §I/§V.
- cmd: `/build` `@build` → ejecuta §T (o un plan). Folda §D al `x`. Corre `verify.sh`. No invoca `/check` ni `/review`.
- cmd: `/check` `@check` → drift spec↔código sobre lo actual. Default §V. `T<n>` acota a las §V/§I que cita esa T y al diff vs la rama base. `--all` es hito. No escribe. Si este hilo implementó, para y pide chat nuevo.
- cmd: `/explore` `@explore` → bosqueja código sin spec
- cmd: `/review` `@review` → auditoría read-only. Si este hilo implementó, para y pide chat nuevo.
- cmd: `/ship` → puerta local + PR, no mergea
- file: `FORMAT.md` schema de SPEC.md
- file: `CLAUDE.md` constitución slim; `.cursor/rules/00-gobernanza.mdc` es su derivado
- file: `.workflow/verify.sh` contrato de verificación
- file: `docs/adr/0002-spec-actual-vs-delta.md` decisión actual vs delta
- file: `apply-sdd.sh` overlay SDD a un proyecto con workflow viejo
- env: ninguno requerido para el loop SDD

## §V INVARIANTS
V1: CLAUDE.md always-on no duplica el SDLC completo. Git flow largo, findings CLI y batch viven fuera de ella.
V2: SPEC.md existe en la raíz con las secciones §G §M §C §I §V §T §B §D en ese orden. §D vacío = header + fila `-`.
V3: `/build` sin argumento de plan ejecuta la siguiente fila §T con status `.` o `~`, citando §V y §I tocados.
V4: Un test o build que falla considera backprop a §B+§V antes de reintentar a ciegas.
V5: `/check` no escribe archivos. Reporta HOLD / VIOLATE / UNVERIFIABLE por cada V<n> en el alcance.
V6: Política de fase `spec` permite escribir `SPEC.md`, `FORMAT.md` y `docs/**`. No código de aplicación.
V7: Default de entrega es PR a `main`. Si `main` no existe y `develop` sí, se usa `develop` (compat).
V8: Graphify no es paso 0 de discovery. Se ofrece al final, o si el usuario lo pide.
V9: `generate-cursor-rules.sh --check` sigue verde: las reglas `.mdc` derivan de `.claude/commands/` + CLAUDE.md.
V10: Convención "funciones < 30 líneas" no forma parte de la constitución. No se exige.
V11: Un cambio que no es verdad todavía se escribe en §D (ADDED/MODIFIED/REMOVED), no reescribiendo §I/§V en el lugar. Corrección de spec que mentía sobre el presente sí es amend live.
V12: `/check` puntúa §I/§V live. Filas abiertas de §D no son MISSING ni VIOLATE. T `x` con §D citada sin foldar es STALE.
V13: `/build` al pasar T → `x` folda las filas §D que citan esa T (ítem a ítem) y las borra de §D. No reescribe la sección entera.
V14: `/build` no invoca `/check` ni `/review`. `/check` y `/review` paran si esta conversación escribió código de aplicación, salvo override explícito del usuario (reporte: `SESGO: mismo hilo que construyó`).
V15: `apply-sdd.sh` copia el andamiaje al destino sin pisar `verify.conf`, `delivery.conf`, un SPEC.md con §G real, ni `CLAUDE.md.pre-sdd` si ya existe. Branch `chore/sdd-workflow` solo desde `main`/`master`/`develop`, o checkout si ya existe. No commitea. Distill de §I/§V queda para `/spec distill`.
V16: `/check T<n>` solo puntúa las §V/§I que cita esa T y los archivos del diff vs la rama base. `--all` es hito (antes de `/ship` o cada varias T). El cierre de `/build` sugiere `/check T<n>`, no `--all`.

## §T TASKS
id|status|task|cites
T1|x|FORMAT.md + SPEC.md de este template|V2
T2|x|CLAUDE.md slim (~200 líneas) + 00-gobernanza derivado|V1,V9
T3|x|/spec /check /explore y reescribir /build al loop §T|V3,V4,V5
T4|x|phase.sh + write-guard: política spec|V6
T5|x|discovery/feature/implement/architect/git-setup alineados a SDD|V8,V3
T6|x|GitHub Flow default en git-setup, ship, pr-body|V7
T7|x|README describe el loop spec→build→check, no el SDLC de 15 fases como camino único|V1
T8|x|tests de política spec + verify.sh verde|V6,V9
T9|x|§D actual vs delta: FORMAT, /spec /build /check /feature, tests, pr-body|V11,V12,V13
T10|x|constructor ≠ auditor: /build no checkea; /check y /review paran si el hilo implementó|V14
T11|x|apply-sdd.sh overlay a proyectos con workflow viejo|V15
T12|x|apply-sdd: no crear branch desde feature; no pisar pre-sdd|V15
T13|x|/check T<n> acotado; --all queda como hito|V16

## §B BUGS
id|date|cause|fix
B1|2026-09-15|apply-sdd hacía `checkout -b` desde cualquier feature y pisaba CLAUDE.md.pre-sdd|V15

## §D DELTA
id|op|target|change|cites
-|-|-|-|-

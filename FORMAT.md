# FORMATO de SPEC.md

Un archivo. Raíz del proyecto. Cada comando SDD lo lee.

La spec se carga en (casi) cada turno. Por eso es corta, addressable, y no se
reparte en `docs/`. Si choca con un plan, un contrato o un ADR, **gana SPEC.md**
hasta que el usuario la enmiende.

## SECCIONES

Orden fijo. Headers fijos. Addressable.

```
# SPEC

## §G GOAL
1-2 frases. Para qué existe este sistema. Es el norte.

## §M MODE
explore | spec | production

## §C CONSTRAINTS
- bala. límite no negociable (stack, legal, "no hacemos X").

## §I INTERFACES
Superficie externa. Lo que el mundo ve **hoy**.
- cmd: `foo bar` → stdout JSON
- api: POST /x → 200 {id}
- file: `config.yaml` schema …
- env: `FOO_KEY` required

## §V INVARIANTS
Numeradas. Testeables. Cada una DEBE sostenerse **hoy**.
V1: ∀ req → auth check before handler
V2: token expiry ≤ ⊥ rejected at exact expiry

## §T TASKS
Tabla pipe. ids monotónicos (nunca se reúsan).
status: `x` hecho / `~` en curso / `.` pendiente
id|status|task|cites
T1|.|scaffold repo|-
T2|.|impl §I.api POST /x|V2,D1

## §B BUGS
Log de backprop. Cada fila = bug + invariante que evita la recurrencia.
id|date|cause|fix
B1|2026-09-11|token `<` not `≤`|V2

## §D DELTA
Propuesto. No es la verdad actual. Vacío = header + fila `-`.
id|op|target|change|cites
D1|ADDED|§I|api: POST /x → 200 {id}|T2
```

Celdas: `|` literal → `\|`. Backticks OK. Vacío = `-`.

## ADDRESSING

`§<S>.<n>` = sección.ítem. `§V.2` = invariante 2.
Commits, PRs y chat referencian por §. Cero ambigüedad.

## ENCODING

Compacto. Fragmentos OK. Preservá verbatim: código, rutas, ids, URLs, números,
strings de error, SQL, regex.

Símbolos (opcionales, no obligatorios):

```
→   lleva a / se vuelve
∴   por lo tanto / arreglo
∀   para todo
∃   existe
!   debe
?   opcional
⊥   nunca / prohibido
≠   distinto
≤ ≥  a lo sumo / al menos
```

Prosa larga en la spec es un bug: se va al reporte (`docs/reviews/`) o al ADR.

## UN ARCHIVO

Proyecto grande → más líneas en las mismas secciones, no más archivos.
Si SPEC.md > 500 líneas, compactá §B (bugs viejos se resumen) antes de partir.

`docs/contracts/` existe para **expandir** un ítem de §I que no cabe. No es
una spec paralela. Si el contrato y §I discrepan, se enmienda SPEC.md.

## ACTUAL VS DELTA

§G §M §C §I §V §T §B = **lo actual**. Cómo se comporta el sistema ahora, o lo
que ya debe sostenerse. Un PR abandonado no debería dejar futuro escrito ahí.

§D = **lo propuesto**. Gramática de diff, no reescritura de sección:

| op | efecto al fold |
|---|---|
| `ADDED` | se agrega el ítem al `target` |
| `MODIFIED` | se reemplaza **ese** ítem (`§V.5`, un bullet de §I). No la sección entera. |
| `REMOVED` | se borra ese ítem |

`cites` = **una** §T. Esa tarea implementa la fila y `/build` la folda al marcar `x`.

```
id|op|target|change|cites
D1|ADDED|§I|api: POST /x → 200 {id}|T2
D2|MODIFIED|§V.5|/check ignora §D. No es MISSING.|T2
D3|REMOVED|§I|cmd: `foo legacy`|T2
```

`change` con `?` = no se folda. Resolvé la duda antes de `x`.

### Qué va a §D y qué a live

| caso | dónde |
|---|---|
| `/spec new` / `distill` | live (baseline). §D vacío. |
| Corregir spec que mentía sobre el presente | live |
| `/spec bug:` (la clase ya debería sostenerse) | live §V + §B; §T del fix |
| Feature / amend que **aún no es verdad** en el código | §D + §T. ⊥ reescribir §I/§V enteros. |
| §G y §M | siempre live. Requieren OK explícito. |
| §C que ata al agente ya (stack elegido) | live |
| §C que será verdad cuando aterrice una §T | §D |

Si no está claro: una pregunta — "¿ya es verdad, o es el cambio?"

### Fold (`/build` al pasar T → `x`)

1. Filas §D cuyo `cites` es esa T.
2. Aplicá la `op` al ítem, no a la sección.
3. Borrá esas filas. Si §D queda vacío, dejá header + `-|-|-|-|-`.
4. Recién ahí `~` → `x`.

Sin fold no hay `x`. T `x` con su §D todavía abierta = STALE en `/check`.

## QUIÉN ESCRIBE QUÉ

| comando | escribe | sección |
|---|---|---|
| `/spec` (new/amend/bug) | crea o edita | live que nombre, o §D si no es actual |
| `/feature` | §D + §T | no reescribe §I/§V live |
| `/build` | status §T **y** fold de §D citada | nada más |
| `/check` | nada | read-only; puntúa live en el alcance (`T<n>` o sección). `--all` es hito |
| `/explore` | código, no spec | — |

`/build` no inventa §I/§V. Si el delta está mal, `/spec` lo corrige.

## CONSTRUCTOR ≠ AUDITOR

El que construye no certifica. El que certifica no escribe. El que no es un
modelo es `verify.sh`.

- `/build` corre `verify.sh` y pega la salida. Eso no es `/check`.
- `/build` no invoca `/check` ni `/review` en el mismo hilo.
- `/check` y `/review` (y `/security` `/ux`) paran si **esta conversación**
  escribió código de aplicación. Piden un chat nuevo, sin el relato del build.
- En Cursor el modelo es el de esa sesión: el chat B usa el modelo fuerte.
- No hay hook que abra el chat. La barrera es la regla en el comando (como
  Cursor sin PreToolUse). Override solo si el usuario escribe que acepta el
  sesgo; el reporte lleva `SESGO: mismo hilo que construyó`.

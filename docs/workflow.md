# Workflow de producción (referencia, no always-on)

Este archivo **no se carga en cada turno**. Lo leen `/ship`, `/deploy`,
`/migrate`, `/review` y quien esté en `SPEC.md` §M = `production`.

El loop de todos los días está en `CLAUDE.md` + `SPEC.md` + `FORMAT.md`.
§I/§V son lo actual; lo propuesto vive en §D hasta que `/build` lo folda.
`/build` no certifica: `verify.sh` en el hilo que construye; `/check` y `/review` en otro chat.

---

## Modos

| Modo | Cuándo | Qué corre |
|------|--------|-----------|
| `explore` | bosquejar, spike, "¿y si...?" | código + `verify.sh`. Sin spec. Al terminar, ofrecer `/spec` distill. |
| `spec` | default. hay SPEC.md | `/spec` → `/build` → `/check T<n>`. `--all` es hito. Backprop a §B+§V si algo falla. |
| `production` | hay usuarios o datos reales | lo de `spec` **más** review/security/migrate/ship, CI, findings con test de regresión. |

El modo vive en `SPEC.md` §M. Lo cambia el usuario (o `/spec amend §M` con su OK).

---

## Git

**Default: GitHub Flow.**

```
main              producción, siempre deployable, tag semver en cada release
 └── feature/*    una branch por cambio. PR a main.
     fix/*        bug no urgente. PR a main.
     hotfix/*     emergencia. branch desde main, PR a main.
```

Nunca se trabaja en `main`. El merge del PR lo hace el humano.

**Opt-in: Git Flow** (`main` + `develop`). Se activa con
`BASE_POR_DEFECTO=develop` en `.workflow/delivery.conf` (lo crea el humano).
Úsalo si el equipo ya integra en `develop` y suelta a `main` por release.

Commits convencionales: `tipo(scope): descripción`. Tipos: `feat`, `fix`,
`docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`, `build`, `revert`.
El hook `commit-msg` lo valida. Referenciar § cuando aplique:
`feat(T3): impl POST /x` o `fix(V2): token expiry ≤`.

---

## Hallazgos (modo production)

Los reportes en markdown llevan la prosa. `docs/findings.json` lleva lo
consultable. `docs/reviews/decisiones.md` se **genera** — no se edita a mano.

```bash
python3 .workflow/findings.py list --abiertos
python3 .workflow/findings.py add --id B3 --severidad blocker \
  --titulo "..." --origen docs/reviews/2026-01-15-api.md
python3 .workflow/findings.py cerrar B3 --commit a1b2c3d \
  --test tests/test_api.py::test_put_es_atomico --probar-regresion
python3 .workflow/findings.py nota B3 "se descartó X porque Y"
```

`cerrar` exige `--test` o `--sin-test --razon`. `--probar-regresion` monta el
árbol padre y comprueba que el test falla sin el arreglo.

Un hallazgo de review y un §B de la spec no son lo mismo: el hallazgo es trabajo
pendiente; §B es memoria de un bug ya entendido + el invariante que lo cierra.
Al cerrar un hallazgo que era un bug de clase, también `/spec bug:`.

---

## Entrega

Dos modos. Los elige el proyecto, no se heredan.

**Local (default):** el agente implementa y para. El humano commitea y mergea.

**PR:** `.workflow/delivery.conf` (lo crea el humano, está protegido):

```
MODO_ENTREGA=pr
AGENTE_PUEDE_PUSHEAR=si
BASE_POR_DEFECTO=main
```

Entonces `/build` puede commitear la branch de trabajo (código+tests, docs
aparte) y `/ship` pushea y abre el PR. Nunca la base. Nunca el merge.

```bash
bash .workflow/ship.sh            # ¿está listo?
bash .workflow/ship.sh --cuerpo   # leer el cuerpo antes
bash .workflow/ship.sh --abrir-pr
```

`batch.sh` (fábrica de PRs en paralelo) exige además `BATCH_HEADLESS=si` y se
lanza a mano. En Cursor no corre: usa `claude -p`.

---

## Migraciones

Expand / migrate / contract. Quitar lo viejo es **otro** release.

```bash
python3 .workflow/check-migrations.py
```

Detalle y marcas `expand-contract:` / `irreversible:` — ver también
`.workflow/check-migrations.py` y la regla 14 de CLAUDE.md.

---

## Verificación

```bash
bash .workflow/verify.sh           # completo
bash .workflow/verify.sh --quick   # sin tests
bash .workflow/verify.sh --strict  # CI: un salto cuenta como fallo
bash .workflow/verify.sh --reusar  # no repetir si la evidencia ya vale
```

| Resultado | Significa |
|-----------|-----------|
| `ok` | verde |
| `parcial` | **no es verde**: nombrar qué quedó sin verificar |
| `falla` | no reportar hasta corregir |

Pasos: `.workflow/verify.conf`. En CI, `CI_SETUP` prepara el runner.

---

## Fases y escritura (Claude Code)

| Política | Fases | Puede escribir |
|----------|-------|----------------|
| `spec` | spec, discovery, architect, contracts, feature | SPEC.md, FORMAT.md, docs/ |
| `docs` | plan, review, security, ux, deploy, ship, check | solo docs/ |
| `tests` | test | tests y docs/ |
| `full` | explore, implement, build, change, migrate, git-setup | no protegidos |

En Cursor no hay hook PreToolUse. El agente respeta la política igual.
`bash .workflow/phase.sh show` dice la fase; `clear` la libera. Caduca a las 12 h.

---

## Capas de protección

Editor (se salta) → hooks de Claude Code (se saltan, y no existen en Cursor) →
git hooks (`--no-verify`) → **CI + CODEOWNERS + branch protection** (no se saltan).

Reemplazá `@TU-USUARIO` en `.github/CODEOWNERS`. Sin eso GitHub ignora el archivo.

---

## Graphify (opcional)

Reduce grep masivo en repos grandes. No es requisito del loop SDD.

```
uv tool install graphifyy && graphify install
# En el asistente: /graphify .   (el CLI `graphify .` no existe)
```

Si `graphify-out/GRAPH_REPORT.md` existe, usalo para navegar. Si está viejo,
el código manda: grep está permitido.

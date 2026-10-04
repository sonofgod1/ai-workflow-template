# 1. Spec-driven development como loop por defecto

Fecha: 2026-09-11

## Estado

Aceptada.

## Contexto

La plantilla nació como un SDLC con 15 fases, constitución always-on de ~850
líneas (duplicada en Cursor con `00-gobernanza`), y la regla "fuera de un
comando, modo consulta: no modificas nada". Eso controla bien a un agente en un
sistema ya en producción. Entorpece dos cosas que la plantilla dice servir:

1. **Spec-driven development.** No había un artefacto vivo que dijera qué debe
   seguir siendo verdad. Había planes por cambio, contratos de API, ADRs y
   findings. Después del merge, la "spec" quedaba partida y el código se
   separaba de ella.
2. **Construir productos.** El vibecoding profesional (instrucción → código →
   tests como juez) estaba prohibido por diseño. El primer día se frenaba en
   graphify y Git flow `main`/`develop`.

El costo de contexto (~20k tokens de proceso duplicado en cada turno de Cursor)
desplazaba al código del proyecto.

## Decisión

- `SPEC.md` en la raíz es la spec de producto (formato en `FORMAT.md`).
- El loop por defecto es `/spec` → `/build` → `/check`. Un bug vuelve a la spec
  (`/spec bug:`) como invariante nuevo, no solo como fix en el código.
- La constitución (`CLAUDE.md` / `00-gobernanza`) se recorta a lo que hay que
  cargar siempre. El SDLC de producción vive en `docs/workflow.md` y en los
  comandos `/review` `/security` `/migrate` `/ship` `/deploy`.
- Tres modos en `SPEC.md` §M: `explore`, `spec`, `production`.
- Fuera de un comando el agente puede escribir código si el usuario lo pidió.
- GitHub Flow (`main` + PR) es el default. `develop` queda como opt-in.
- Graphify es opcional, nunca el paso 0.

## Consecuencias

- Los comandos `/discovery` `/architect` `/contracts` `/plan` `/implement`
  `/feature` siguen existiendo. Dejan de ser el camino único: alimentan o
  ejecutan la spec.
- Los proyectos que ya usan `develop` siguen funcionando: `ship.sh` detecta la
  base, y `BASE_POR_DEFECTO=develop` en `delivery.conf` la fija.
- Cursor sigue sin PreToolUse. La constitución slim nombra esa brecha. La
  barrera real sigue siendo CI + branch protection.
- Hay que mantener `generate-cursor-rules.sh` alineado a un CLAUDE.md corto.

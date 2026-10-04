# 2. Spec actual vs delta

Fecha: 2026-09-11

## Estado

Aceptada.

## Contexto

ADR 1 dejó `SPEC.md` como spec viva. El amend in-place escribía el futuro en
§I/§V: `POST /x` aparecía como superficie actual y `/check` lo marcaba MISSING
hasta `/build`. Un PR abandonado dejaba el norte mintiendo. Dos cambios a la
misma sección se pisaban.

OpenSpec separa specs del sistema (hoy) y deltas por cambio (ADDED / MODIFIED /
REMOVED) que se fusionan al archivar. El harness (`openspec/`, CLI, proposal.md
+ design.md + tasks.md) reintroduce artefactos en paralelo a §T.

## Decisión

- §G §M §C §I §V §T §B describen lo **actual**.
- Lo que aún no es verdad vive en §D, en el mismo `SPEC.md`, con ops
  `ADDED` / `MODIFIED` / `REMOVED` a nivel de ítem.
- `/build` folda las filas §D citadas al marcar la §T `x`. No hay carpeta
  `changes/`, ni CLI npm, ni artefactos extra.
- `/check` puntúa lo actual. §D abierto no es drift. T `x` con §D citada
  sin foldar es STALE.
- §G y §M nunca van a §D: son decisión de producto, live, con OK explícito.

Detalle operativo: `FORMAT.md` § ACTUAL VS DELTA.

## Consecuencias

- `/spec amend` y `/feature` dejan de reescribir §I/§V por un cambio futuro.
- Dos branches en paralelo conflictúan en §D, no silencian un rewrite de §I.
- `pr-body.py` puede listar el delta en el PR para revisión humana.
- No se parte la spec por dominio. Sigue un archivo; a las 500 líneas se
  compacta §B, como ya decía FORMAT.md.

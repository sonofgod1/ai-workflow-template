<!-- GENERADO por .workflow/findings.py — NO EDITAR A MANO.
     Cualquier cambio aquí se pierde en el próximo add/cerrar/estado.

     La prosa vive en dos sitios, no en este archivo:
       - el reporte de review (docs/reviews/*.md): síntoma, por qué importa, sugerencia
       - la nota del hallazgo: python3 .workflow/findings.py estado I2 \
             --nuevo descartado --nota "el caso no puede ocurrir porque ..."

     Regenerar a mano: python3 .workflow/findings.py decisiones
     Comprobar que está al día (CI): python3 .workflow/findings.py decisiones --check
-->

# Decisiones de triaje

*Estado de cada hallazgo, generado desde `docs/findings.json`.*

**4 hallazgo(s):** 3 sin cerrar, 1 resuelto(s), 0 descartado(s).


## 🟠 Importantes sin cerrar

| ID | Título | Archivo(s) | Estado | Origen | Nota |
|---|---|---|---|---|---|
| I1 | Una branch de chore no tiene ningún comando que sea dueño de su commit | `CLAUDE.md`, `.workflow/ship.sh`, `sync-workflow.sh` | abierto | [reporte](docs/reviews/2026-09-11-validacion-modo-pr.md) | — |
| I2 | +docs/contracts/** frena a /build ante un cambio que solo precisa la prosa del contrato | `.claude/protected.txt`, `.claude/commands/plan.md`, `.claude/commands/build.md` | abierto | [reporte](docs/reviews/2026-09-11-validacion-modo-pr.md) | CONFIRMADO en campo 2026-09-11 con el plan de B4 en musicos, y es peor de lo que decía el reporte. (1) El hook NO tiene vía de aprobación: su propio mensaje dice 'Un contrato solo cambia si el usuario lo aprueba' y no existe ni env var ni flag para aprobarlo — /build le ofreció al usuario una salida inejecutable. (2) /contracts tampoco puede: .claude/commands/contracts.md:14 dice 'No modifica contratos existentes SIN NOTIFICAR al usuario', o sea que se cree capaz de enmendar avisando, y el hook lo bloquea igual. El comando y el hook no se hablan. (3) Causa raíz, más nítida que en el reporte: el prefijo '+' le aplica semántica de ADR (inmutable, se reemplaza por otro) a un contrato, que es un documento VIVO que cambia con cada endpoint. Para docs/adr/** el '+' es correcto; para docs/contracts/** deja api.md intocable por cualquier agente para siempre, y /contracts sirve el primer día y nunca más. Salida usada: el humano aplicó las ediciones a mano con un script preparado aparte. Confirmado también que /build obedece la regla 13: paró, lo dijo, y no commiteó nada. |

## 🟡 Sugerencias sin cerrar

| ID | Título | Archivo(s) | Estado | Origen | Nota |
|---|---|---|---|---|---|
| S1 | findings.py no deja agregar una nota sin cambiar también el estado | `.workflow/findings.py` | abierto | [reporte](docs/reviews/2026-09-11-validacion-modo-pr.md) | — |

## ✅ Resueltos

| ID | Título | Commit | Test | Fecha |
|---|---|---|---|---|
| B1 | check-regression.py falla abierto: cualquier runner que no sea pytest declara CONFIRMADA ante un exit desconocido | `9725d57` | ✅ probado — `.workflow/tests/test-check-regression.py` | 2026-09-11 |

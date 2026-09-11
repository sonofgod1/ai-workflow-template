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

**7 hallazgo(s):** 1 sin cerrar, 6 resuelto(s), 0 descartado(s).


## 🟡 Sugerencias sin cerrar

| ID | Título | Archivo(s) | Estado | Origen | Nota |
|---|---|---|---|---|---|
| S2 | el cuerpo del PR exige plan a una branch de andamiaje, que por diseño no lo tiene | `.workflow/pr-body.py` | abierto | [reporte](docs/reviews/2026-09-11-validacion-modo-pr.md) | Detectado en el PR #6 de musicos: ofrecía los planes de B4 y B2 como candidatos de un sync de tooling. |

## ✅ Resueltos

| ID | Título | Commit | Test | Fecha |
|---|---|---|---|---|
| B1 | check-regression.py falla abierto: cualquier runner que no sea pytest declara CONFIRMADA ante un exit desconocido | `9725d57` | ✅ probado — `.workflow/tests/test-check-regression.py` | 2026-09-11 |
| B2 | sync --commit no ve lo que escribió la corrida anterior, que es la del auto-update | `c3707d7` | ✅ probado — `.workflow/tests/test-sync-commit.py` | 2026-09-11 |
| I1 | Una branch de chore no tiene ningún comando que sea dueño de su commit | `e0d1cbd` | ✅ probado — `.workflow/tests/test-sync-commit.py` | 2026-09-11 |
| I2 | +docs/contracts/** frena a /build ante un cambio que solo precisa la prosa del contrato | `56cf02b` | ✅ probado — `.workflow/tests/test-check-protected.py` | 2026-09-11 |
| I3 | sync-workflow.sh nunca entra al manifest, así que --commit no puede commitear su propia actualización | `defccac` | ✅ probado — `.workflow/tests/test-sync-commit.py` | 2026-09-11 |
| S1 | findings.py no deja agregar una nota sin cambiar también el estado | `99fea41` | ✅ probado — `.workflow/tests/test-findings-cli.py` | 2026-09-11 |

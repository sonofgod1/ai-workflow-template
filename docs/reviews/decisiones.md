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

**4 hallazgo(s):** 0 sin cerrar, 4 resuelto(s), 0 descartado(s).


## ✅ Resueltos

| ID | Título | Commit | Test | Fecha |
|---|---|---|---|---|
| B1 | check-regression.py falla abierto: cualquier runner que no sea pytest declara CONFIRMADA ante un exit desconocido | `9725d57` | ✅ probado — `.workflow/tests/test-check-regression.py` | 2026-09-11 |
| I1 | Una branch de chore no tiene ningún comando que sea dueño de su commit | `e0d1cbd` | ✅ probado — `.workflow/tests/test-sync-commit.py` | 2026-09-11 |
| I2 | +docs/contracts/** frena a /build ante un cambio que solo precisa la prosa del contrato | `56cf02b` | ✅ probado — `.workflow/tests/test-check-protected.py` | 2026-09-11 |
| S1 | findings.py no deja agregar una nota sin cambiar también el estado | `99fea41` | ✅ probado — `.workflow/tests/test-findings-cli.py` | 2026-09-11 |

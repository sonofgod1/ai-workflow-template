# Parches de archivos protegidos — 2026-09-08 — APLICADOS

Este archivo listaba los parches a `.github/workflows/ci.yml` y `CLAUDE.md` que
estaban pendientes de aprobación por estar en `.claude/protected.txt`.

**Ya están aplicados**, con autorización explícita del usuario, que señaló el punto
de fondo: este repositorio **es** el andamiaje, no un proyecto gobernado por él. Aquí
`CLAUDE.md` y `ci.yml` son el producto, no archivos protegidos del proyecto.

## Lo que se aplicó

**`.github/workflows/ci.yml`** — jobs `hallazgos` y `verificacion`.

**`CLAUDE.md`** — reglas duras 12 (evidencia) y 13 (fase activa); secciones
"Verificación y evidencia", "Fases y política de escritura" y "Subagentes"; índice
de hallazgos; tabla de fases con columna de modelo y las filas de `/plan` y `/build`;
`docs/plans/` en el árbol de documentación.

## Lo que queda pendiente de decisión tuya

**I3** — `check-bash.sh` bloquea comandos que solo *mencionan* un patrón peligroso.
Ver `docs/reviews/2026-09-08-enforcement.md`. No se tocó: bajarle la agresividad a un
control de seguridad es decisión del dueño del repo.

Este archivo se puede borrar cuando I3 esté resuelto.

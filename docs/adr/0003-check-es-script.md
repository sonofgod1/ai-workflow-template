# 3. /check es un script, no una segunda sesión

Fecha: 2026-10-06

## Estado

Aceptada. Supera, en el punto de la certificación, a
[0001](0001-spec-driven-development.md).

## Contexto

`/check` le pedía a un modelo fuerte, en un chat nuevo, que releyera el
repositorio y puntuara cada §V. La suite ya había corrido. La segunda sesión
no agregaba corrección y trababa el PR: el build terminaba y el siguiente
paso era otra lectura del backend.

## Decisión

- `verify.sh` certifica la tarea.
- `/check` es `.workflow/check-spec.py`. HOLD si existe `test_v<n>` y
  `.last-verify.json` es `ok` de este árbol. UNVERIFIABLE si no hay test.
  No lee código de aplicación.
- El cierre de `/build` es `/ship`. `/review` queda opt-in, sobre el diff.

## Consecuencias

- Una §V sin test nombrado `test_v<n>` sale UNVERIFIABLE. Ese es el hallazgo.
- `CLAUDE.md` de un proyecto ya instalado no se sincroniza: hay que enmendar
  a mano la frase que manda el check a otro chat, y regenerar
  `00-gobernanza.mdc`.

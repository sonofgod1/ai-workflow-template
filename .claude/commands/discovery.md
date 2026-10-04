---
description: Entender el problema y llenar SPEC.md §G/§C/§M. No escribe código.
model: opus
---

Estás en **fase de descubrimiento**. Tu rol: escuchar antes de especificar.

**Restricciones:**
- ❌ No escribís código de aplicación
- ❌ No proponés stack todavía (eso es `/architect`, y solo si §C no lo tiene)
- ✅ Preguntas, clasificás, llenás SPEC.md
- ✅ Una pregunta a la vez

---

## Fase activa

```bash
bash .workflow/phase.sh set discovery
```

Política: SPEC.md, FORMAT.md, docs/. Al terminar: `bash .workflow/phase.sh clear`

---

## Paso 0 — Herramientas (no bloquea)

```bash
bash .workflow/check-tools.sh
```

Mostrá lo que falte. No pares el descubrimiento por una herramienta opcional.

---

## Paso 1 — El problema, no el stack

Si el usuario ya dijo el propósito en 1-2 frases, usalo. Si no, **una** pregunta:

> ¿Qué problema resuelve esto, en una oración, para quién?

Esa respuesta **es** §G. Redactala concreta (propósito, no lista de features).
Confirmá el texto exacto antes de escribirlo. El norte es decisión de producto.

Mal: "gestionar usuarios, pagos y reportes."
Bien: "que un coordinador asigne turnos sin dobles reservas, reemplazando la hoja de cálculo."

---

## Paso 2 — Clasificar (para §C, no para inflar el proceso)

Tipo de proyecto, en una pasada. Si hay código, mirá archivos (`package.json`,
`pyproject.toml`, carpetas). No exijas graphify.

Composición: `fullstack-monorepo` | `backend-only` | `frontend-only` | `cli` |
`library` | `mobile` | `etl-pipeline` | `microservices` | `otro`.

Componentes principales: las carpetas que de verdad existen o se van a crear.

Modo §M:
- idea / spike → `explore` y ofrecé `/explore`
- vamos a construir el producto → `spec` (default)
- ya hay usuarios o datos reales → `production`

---

## Paso 3 — Escribir la spec

Si no hay SPEC.md, creala (formato FORMAT.md) con:
- §G el norte confirmado
- §M el modo
- §C tipo de proyecto, componentes, restricciones que el usuario dijo
- §I / §V / §T vacíos o con lo que ya se sepa (sin inventar)
- §B header solo
- §D header + fila `-` (vacío: esto es baseline, no un cambio)

Si ya hay SPEC.md, **amend §G/§C/§M** — no reescribas §V/§T/§I.

Opcional: `docs/discovery/01-problem.md` con problema, usuario, no-goals, riesgos.
La spec manda; este archivo es memoria humana.

No copies §G a CLAUDE.md. CLAUDE.md apunta aquí.

---

## Paso 4 — Graphify (opt-in, al final)

Solo si el repo ya tiene código y el usuario quiere un mapa:

```
uv tool install graphifyy && graphify install
# En el asistente: /graphify .
```

Si dice que no, no lo menciones más.

---

## Al terminar

> Descubrimiento listo.
> - §G: [una línea]
> - §M: [explore|spec|production]
> - Composición: [tipo + componentes]
> - Siguiente: `/spec` para §I/§V/§T, o `/architect` si hay que elegir stack, o `/build --next` si §T ya tiene trabajo.
>
> Graphify: [instalado / lo saltamos / no aplica]

---
description: Atajo a build --next. Preferí el comando build. Se conserva por hábito.
argument-hint: "[ID de hallazgo, §T.n, o descripción corta]"
model: sonnet
---

Estás en **fase de implementación**. Este comando es un atajo. El camino real es `/build`.

Pedido: **$ARGUMENTS**

```bash
bash .workflow/phase.sh set implement
```

Al terminar: `bash .workflow/phase.sh clear`

---

## Qué hacer

1. Si el pedido es un `§T.n`, un `--next`, o está vacío y existe SPEC.md → ejecutá
   **exactamente** las instrucciones de `/build` (camino SPEC). No re-inventes un plan largo.
2. Si el pedido es un ID de hallazgo (`B3`, `I1`) y el proyecto está en modo
   production → leé el hallazgo, anclá a §G, y tratá el arreglo como una §T implícita:
   citá §V que aplica; si ninguna aplica, el cierre incluye `/spec bug:`.
3. Si no hay SPEC.md → no implementes "igual". Ofrecé `/explore` (spike) o `/spec new`.

**Anclaje a §G** (una línea) antes de tocar código. Si §G está `[pendiente]`, pará:
hace falta `/spec`, no un norte inventado.

Fix trivial (< 10 líneas, 1 archivo, sin decisión de producto): hacelo en el mismo
turno, con la línea de anclaje arriba. No pidas aprobación de un plan ceremonial.

No instales deps sin avisar. No commitas salvo modo PR. No ensanches el scope.
Si encontrás algo roto fuera de lo pedido: pará y reportá, no lo arregles de paso.
Al cerrar: `verify.sh` y chat nuevo para `/check T<n>`. `--all` es hito, no el default. No certifiques en este hilo.

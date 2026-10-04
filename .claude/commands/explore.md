---
description: Bosquejá código sin spec. Spike, prototipo, "¿y si...?".
argument-hint: "[qué explorar]"
model: sonnet
---

Estás en **fase explore**. Tu rol: probar una idea en código, rápido, sin fingir que hay una spec.

Pedido: **$ARGUMENTS**

**Restricciones:**
- ✅ Escribís código y tests
- ✅ Corrés `verify.sh` (o `--quick`) antes de decir "funciona"
- ❌ No inventás SPEC.md de contrabando. Si la idea se queda, `/spec distill`
- ❌ No abras `/review` `/security` `/ship` desde acá
- ❌ No instales deps sin avisar (regla 4)

---

## Fase activa

```bash
bash .workflow/phase.sh set explore
```

Escritura: full (respetando protegidos). Al terminar: `bash .workflow/phase.sh clear`

---

## Cómo trabajar

1. Si el pedido es ambiguo, **una** pregunta. Si se puede bosquejar, bosquejá.
2. Alcance chico: un spike que se pueda tirar. No arquitectures el producto.
3. Si ya existe SPEC.md, leé §G y §C. No los contradigas en silencio. Si el spike los tensiona, dilo al final.
4. No pidas aprobación de un plan de 40 líneas. Mostrá qué vas a tocar en 5 viñetas y hacelo en el mismo turno, salvo que haya una decisión de producto real.
5. Al terminar: `bash .workflow/verify.sh --quick` (o completo si escribiste tests). Pegá la salida.
6. Cierre obligatorio — una de estas:

```
Spike listo. Tres salidas:
1. Tirarlo (fue aprendizaje).
2. /spec distill — esto se queda, hay que especificarlo.
3. Seguir explorando: [qué falta].
```

Si el usuario ya dijo "esto es el producto", no explores: `/spec new` y después `/build`.

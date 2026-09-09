---
description: Investiga y produce un plan ejecutable, con detalle a nivel de cambio. No escribe código.
argument-hint: [ID del hallazgo o descripción de la feature]
model: opus
---

Estás en **fase de planificación**. Tu rol: arquitecto que investiga antes de decidir.

Solicitud: **$ARGUMENTS**

**Restricciones:**
- ❌ No escribes código de producción
- ❌ No implementas nada, ni siquiera "lo trivial"
- ✅ Investigas, decides, y dejas un plan que otro pueda ejecutar sin volver a investigar

---

## Fase activa — antes de cualquier otra cosa

```bash
bash .workflow/phase.sh set plan
```

Esto declara la fase y activa su política de escritura: en `/plan` los hooks
bloquean cualquier escritura fuera de `docs/`.

Si un bloqueo te detiene, **no lo rodees**. Significa que estás saliéndote de lo
que esta fase puede hacer. Para, dilo, y espera instrucción.

Al terminar, libera la fase: `bash .workflow/phase.sh clear`

---

## Por qué existe esta fase separada de la implementación

Cuando investigar, decidir e implementar ocurren en el mismo turno, la calidad del
plan depende de lo que quepa en el contexto después de haber leído el código. Y el
plan que sale es a nivel de archivo ("modificar `api.py`"), que no es ejecutable:
quien implementa todavía tiene que decidir el diseño.

Aquí se separan. Tú investigas con todo el contexto disponible y produces un plan
con detalle **a nivel de cambio**: qué función, qué firma, qué comportamiento antes
y después. Ese plan es lo único que `/build` va a leer. Si el plan es ambiguo,
`/build` va a improvisar, y ahí es donde se rompe todo.

**La prueba de si tu plan está terminado:** ¿podría ejecutarlo alguien que no haya
leído este código y no pueda preguntarte nada? Si no, todavía no está terminado.

---

## Paso 0 — Anclar al norte del proyecto

Lee la sección **"Norte del proyecto"** de `CLAUDE.md`. Antes de investigar nada,
declara cómo el cambio solicitado sirve a ese norte. Tres salidas:

1. **Encaja** → nombra la conexión en una línea y continúa al Paso 1.
2. **Se desvía** → el cambio es localmente razonable pero no sirve al norte o lo
   contradice. **Para en seco:**
   ```
   ⚠️ Tensión con el norte del proyecto
   - Norte documentado: [cita la frase del norte]
   - Lo que se pidió: [el cambio]
   - Por qué no encaja: [la desconexión concreta]
   - No planifico hasta que me digas cómo proceder.
   ```
3. **El norte quedó corto** → **Para en seco.** No edites `CLAUDE.md`. Propón la
   redefinición como decisión de producto y espera aprobación:
   ```
   ⚠️ Creo que el norte del proyecto quedó corto
   - Norte actual: [cita la frase del norte]
   - Por qué creo que quedó corto: [razón concreta]
   - Redefinición que propongo: [nuevo texto, 1-2 frases]
   - Esto es una decisión tuya. No toco nada hasta que apruebes.
   ```

**Regla dura 9:** nunca redefinas el norte silenciosamente.

---

## Paso 1 — Contexto mínimo, antes de investigar

Lee, en este orden:

1. `CLAUDE.md` — reglas duras y **la sección "Tipo de proyecto"**, que define qué
   componentes estructuran el plan
2. `graphify-out/GRAPH_REPORT.md` si existe — para saber dónde mirar, y qué son god nodes
3. El hallazgo en `docs/reviews/`, o el archivo de la feature en `docs/features/`
4. Los contratos en `docs/contracts/` que el cambio pueda tocar

No leas el código todavía. Eso es el paso 2, y no lo haces tú.

---

## Paso 2 — Investigación en paralelo

Formula entre **3 y 5 preguntas concretas** cuyas respuestas necesitas para decidir.
Buenas preguntas de investigación son específicas y verificables:

- "¿Cómo se valida hoy la propiedad de un recurso en los endpoints de escritura, y
  dónde vive esa lógica?"
- "¿Qué componentes consumen el formato de error actual de la API?"
- "¿Existe ya un helper para esto, o se resolvió ad-hoc en cada sitio?"
- "¿Qué cubre la suite de tests actual sobre esta zona?"

Malas: "¿cómo funciona el backend?" (demasiado ancha), "¿qué deberíamos hacer?"
(eso lo decides tú, no la investigación).

**Lanza un agente `researcher` por pregunta, todos en el mismo mensaje** para que
corran en paralelo. Cada uno devuelve conclusiones con `ruta:línea`, no archivos
enteros: tu contexto se queda limpio para decidir.

Si tu editor no soporta subagentes, responde tú las mismas preguntas, una por una,
y **resume cada respuesta antes de pasar a la siguiente**. El objetivo es el mismo:
llegar al plan con conclusiones, no con material crudo.

**No lances un researcher para confirmar algo que ya sabes.** Si vienes de trabajar
en esa zona del código y la respuesta ya está en tu contexto, escríbela directamente
en la sección "Estado actual" del plan y di de dónde la sacaste. El fan-out existe
para no leer 200 archivos, no como ritual: un researcher que va a devolver lo que ya
tienes cuesta tiempo y no añade nada.

Si la investigación contradice lo que decía el hallazgo o la feature, dilo
explícitamente antes de planificar. Es información valiosa, no un estorbo.

---

## Paso 3 — Escribir el plan

Guarda en `docs/plans/YYYY-MM-DD-[slug].md`. **Con este formato**, adaptando las
secciones de componentes a lo que diga "Tipo de proyecto" en `CLAUDE.md`:

```markdown
# Plan: [título] — [fecha]

## Anclaje al norte
[Una línea: cómo este cambio sirve al norte del proyecto.]

## Origen
[ID del hallazgo o ruta del archivo de feature. Y qué se pidió, en 2 líneas.]

## Estado actual — lo que encontró la investigación
[Qué es verdad hoy sobre el código en esta zona, con `ruta:línea`. Incluye lo que
NO existe: evita que quien implemente asuma que algo está ahí.]

## Decisión de diseño
[Qué se va a hacer y por qué esta forma y no otra. Si descartaste una alternativa
razonable, nómbrala y di por qué. Dos o tres párrafos, no más.]

## Cambios — [Componente 1, ej. Backend]

### `ruta/archivo.py`
- **Qué toca:** `nombre_de_la_funcion()` (línea ~88) / archivo nuevo
- **Firma antes:** `def asignar(musico_id: int) -> None`
- **Firma después:** `def asignar(musico_id: int, forzar: bool = False) -> Asignacion`
- **Comportamiento antes:** [una o dos líneas]
- **Comportamiento después:** [una o dos líneas]
- **Casos de borde a respetar:** [los que la investigación encontró]

### `ruta/otro.py`
[misma estructura]

## Cambios — [Componente 2, ej. Frontend]
[misma estructura, o "ninguno" con la justificación de por qué no hace falta]

## Contratos afectados
[Qué cambia en `docs/contracts/`, o "ninguno". Si cambia un contrato, el plan debe
decir si eso requiere pasar por `/contracts` antes de construir.]

## Migraciones
[Si hay cambio de schema: qué migración, si es reversible, y si es compatible con
la versión anterior de la aplicación mientras dura el despliegue. Si no hay: "ninguna".]

## Tests que deben existir al terminar
- [ ] [test concreto: qué entrada, qué se espera]
- [ ] **El test de regresión**: [ruta::nombre] — falla hoy, pasa después.
      Nómbralo con la entrada exacta que reproduce el fallo, no una cómoda: es lo
      que `findings.py cerrar --probar-regresion` va a comprobar contra el árbol
      sin el arreglo, y si pasa sin él, el cierre se rechaza.

## Criterio de terminado
- `bash .workflow/verify.sh` en `ok`
- Los tests de arriba existen y pasan
- El test de regresión falla sin el arreglo (`check-regression.py` en `confirmada`)
- [cualquier otra condición concreta]

## Plan de prueba manual
| # | Acción | Resultado esperado | Cómo verificar |
|---|--------|-------------------|----------------|

## Riesgos y efectos secundarios
[Qué puede romperse fuera del scope directo. O "ninguno".]

## Lo que este plan NO hace
[Scope explícitamente excluido, para que `/build` no lo amplíe por su cuenta.]
```

---

## Paso 4 — Presentar y esperar

En el chat, **no repitas el plan entero**. Da:

```
## Plan listo: docs/plans/[archivo]

**Anclaje al norte:** [una línea]
**Decisión de diseño:** [dos líneas — el qué y el porqué]
**Alcance:** [N archivos en [componentes]]
**Contratos:** [afectados o ninguno]
**Migraciones:** [sí, descripción / ninguna]

**Decisiones de producto que necesito antes de construir:**
❓ [pregunta concreta]
- Opción A: [qué implica]
- Opción B: [qué implica]
- Mi recomendación: [A o B con razón de una línea]

[Si no hay: "ninguna — el plan está listo para ejecutar"]

**Riesgo principal:** [uno, el que más importa. O "ninguno".]
```

**Espera aprobación.** No ejecutes el plan tú mismo: para eso está `/build`, que
corre en un modelo más barato precisamente porque este plan ya tomó las decisiones.

Cuando el usuario apruebe:

> Plan aprobado. Ejecuta `/build docs/plans/[archivo]`.

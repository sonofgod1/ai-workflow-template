# Review: el modo PR medido contra un proyecto real — 2026-09-11

**Origen:** validación del workflow ejecutando musicos de punta a punta (PRs #2 y #3
mergeados, plan de B4 aprobado). No es una lectura del código de la plantilla: son dos
lugares donde el ciclo se frenó de verdad y el humano tuvo que tapar el hueco a mano.

Los dos hallazgos comparten causa: **el modo PR modela el trabajo como "un hallazgo → un
plan → `/build` → `/ship`", y todo lo que no tiene esa forma se cae del ciclo.** La promesa
del modo es bajar las acciones humanas por hallazgo de ~10 a 2. Cada vez que un cambio no
encaja en ese molde, las acciones vuelven a subir sin que nada lo advierta.

---

## I1 — una branch de chore no tiene ningún comando que sea dueño de su commit

**Síntoma.** En musicos, `chore/sync-workflow` traía el andamiaje sincronizado más el port
de dos reglas duras a `CLAUDE.md`. Al momento de commitear, el agente no tenía con qué
autorizarse: la excepción de la regla dura 3 nombra a `/build` (commitea código y docs) y a
`/ship` (pushea y abre el PR), y esa branch nunca pasó por `/plan` → `/build` porque no
nace de un hallazgo. `/ship` no commitea por diseño — exige árbol limpio. El commit lo
terminó haciendo el humano a mano.

**Por qué importa.** Es exactamente la acción que el modo PR existe para sacar del medio, y
reaparece en el único tipo de branch que *todos* los proyectos van a tener: la del sync del
andamiaje. Peor, no falla ruidosamente: `/ship` simplemente dice "árbol sucio" y el humano
completa el paso sin registrar que el modo no lo cubrió. Un agujero que se tapa solo es un
agujero que nadie arregla.

**Sugerencia.** Dos caminos, y hay que elegir uno explícitamente:

1. Ampliar la excepción de la regla dura 3 para que `/ship` pueda commitear un árbol sucio
   **cuando el diff toca solo rutas de andamiaje** (`.workflow/`, `.claude/`, `git-hooks/`,
   `CLAUDE.md`) y no hay plan asociado. Acotado y verificable por el propio script.
2. Darle a `sync-workflow.sh` su propio cierre: que commitee lo que sincronizó, con un
   mensaje `chore:` derivado de la lista de archivos que tocó. Es el que ya sabe qué cambió
   y por qué.

La opción 2 es más limpia: pone la autorización en el script que hace el cambio, en vez de
ensanchar el permiso de `/ship` con una condición que hay que mantener.

**No confundir con:** el commit de `CLAUDE.md` que el clasificador de auto mode bloquea.
Ese bloqueo es deliberado y se decidió mantener. Este hallazgo es sobre el commit de los
archivos de andamiaje, que nadie discutió.

---

## I2 — `+docs/contracts/**` bloquea a `/build` ante un cambio que solo precisa la prosa

**Síntoma.** El plan de B4 (`docs/plans/2026-09-11-b4-zona-horaria-iglesia.md`) necesita
precisar en `docs/contracts/api.md` que "hoy" significa el día de calendario en
`America/Mexico_City`, y dejar constancia en `env.md` de que la zona **no** es una env var.
Ningún campo, tipo ni código de estado cambia — el plan concluye, con razón, que no hace
falta pasar por `/contracts`. Pero `.claude/protected.txt:28` marca `+docs/contracts/**`
como **solo-creación**, y los dos archivos ya existen: el hook va a frenar a `/build` a
mitad de ejecución.

**Por qué importa.** La protección discrimina **por archivo**; la decisión que quiere
proteger es **por tipo de cambio**. Cambiar la forma de un contrato (un campo, un status,
un tipo) es una decisión de producto y merece la guardia. Precisar la semántica de una
palabra que el código ya implementa es documentación, y es justo lo que no debería quedar
sin hacer: el costo de que `/build` se frene ahí es que el contrato queda mintiendo hasta
que alguien lo retome por separado. La guardia empuja al resultado que menos queremos.

Hay además un modo de falla peor que el bloqueo: `/build` se detiene **después** de haber
escrito el código, con la branch a medias. El plan y el hook no se hablan — nada avisa al
aprobar el plan que su lista de archivos incluye uno que el agente no va a poder tocar.

**Sugerencia.** Dos cosas, independientes:

1. **Chequeo temprano:** que `/plan` (o `/build` al arrancar) contraste la lista de archivos
   del plan contra `protected.txt` y lo declare **antes** de escribir nada. Que el humano
   sepa al aprobar que el plan incluye dos archivos que va a tener que aplicar él, en vez de
   descubrirlo a mitad de camino. Esto vale para cualquier ruta protegida, no solo contratos.
2. **Distinguir los dos tipos de cambio.** Alternativas, en orden de preferencia:
   - Que el plan declare `contratos: semántica` vs `contratos: forma`, y que solo el segundo
     exija `/contracts` — el hook lee esa declaración del plan que el humano ya aprobó.
   - Partir la protección: `docs/contracts/*.md` solo-creación para la sección de esquemas, y
     una sección de notas que sí sea escribible. Frágil: depende de una convención dentro
     del archivo.
   - Dejarlo como está y aceptar que los contratos los edita el humano. Es la salida honesta
     si no se quiere más maquinaria, pero entonces conviene que el plan lo diga desde el
     principio, que es el punto 1 igual.

**Medido, no supuesto.** `sed -n '1,32p' .claude/protected.txt` en musicos confirma la
semántica del prefijo `+` ("el agente puede crear archivos nuevos ahí, pero no modificar los
que ya existen"), y `docs/contracts/api.md` y `env.md` existen desde `/contracts`.

---

## Confirmación en campo de I2 — 2026-09-11, ejecutando el plan de B4

`/build` corrió el plan completo y **paró en el hook**, tal como se predijo. Obedeció la
regla dura 13 sin intentar rodearlo, no commiteó nada, y dejó el resto verificado
(`parcial` solo por `lint-frontend`; 133 tests en verde; `ruff check backend` en 0 con
`DTZ011`/`DTZ007` ya encendidas). Eso confirma que el modo de falla es el descrito: **código
escrito, contrato sin escribir, branch a medias, y nada que lo avisara al aprobar el plan.**

Lo que la ejecución agregó, y que el reporte original no tenía:

1. **El hook no tiene vía de aprobación.** Su mensaje dice *"Un contrato solo cambia si el
   usuario lo aprueba"* y **no existe ningún mecanismo para aprobarlo** — ni variable de
   entorno, ni flag, ni excepción. `/build`, leyendo ese mensaje, le ofreció al usuario
   "apruebas ahora que edite directamente" como opción: una salida inejecutable. Un mensaje
   de error que promete una puerta que no existe manda al agente a proponer imposibles.

2. **`/contracts` tampoco puede.** `.claude/commands/contracts.md:14` dice *"No modifica
   contratos existentes **sin notificar al usuario**"* — se cree capaz de enmendar avisando.
   El hook lo bloquea igual. **El comando y el hook no se hablan**, y la salida que el propio
   flujo documenta como correcta está cerrada.

3. **La causa raíz, más nítida.** El prefijo `+` le aplica a un contrato la semántica de un
   ADR: inmutable, se reemplaza por otro. Para `docs/adr/**` es correcto y debe quedarse. Un
   contrato es un documento **vivo** que cambia con cada endpoint; bajo esta regla `api.md`
   queda intocable por cualquier agente para siempre, y `/contracts` sirve el primer día del
   proyecto y nunca más.

**Salida que se usó:** el humano aplicó las dos ediciones a mano, con un script preparado
aparte que falla sin escribir si alguna ancla no coincide. Misma forma que el port de
`CLAUDE.md`.

**Esto reordena las sugerencias de I2.** El punto 1 (chequeo temprano del plan contra
`protected.txt`) sigue valiendo tal cual. El punto 2 se simplifica: la corrección mínima es
**sacar `docs/contracts/**` del prefijo `+`** y protegerlo como cualquier otra ruta —
requiere confirmación del usuario, no prohibición absoluta — dejando el `+` solo para
`docs/adr/**`, donde la semántica de inmutabilidad es real. Y separado de eso, el mensaje
del hook no debe prometer una aprobación que no implementa.

---

## S1 — `findings.py` no deja agregar una nota sin cambiar también el estado

**Síntoma.** Para dejar la confirmación en campo de I2 en el índice hubo que correr
`findings.py estado I2 --nuevo abierto --nota "..."`: declarar un cambio de estado que no
existe (de `abierto` a `abierto`) porque `--nuevo` es obligatorio y `add` no acepta `--nota`.
Anotar un hallazgo es lo más frecuente que se le hace a uno; cambiarle el estado, lo menos.

**Por qué importa.** No rompe nada, pero empuja al camino de menor resistencia equivocado:
si anotar cuesta una ceremonia rara, la nota termina solo en el reporte y el índice —que es
lo que CI valida y lo que alimenta `decisiones.md`— se queda sin el porqué. Es la misma
clase de fricción que el resto de la CLI ya tiene registrada (`add` sin `--nota`,
`--archivos` separado por espacios y no por comas, sin forma de cambiar la severidad).

**Sugerencia.** Un subcomando `findings.py nota <id> "texto"`, y que `--nuevo` deje de ser
obligatorio en `estado` cuando venga `--nota`. Conviene resolverlo junto con lo demás de la
CLI, no suelto.

---

## B1 — `check-regression.py` falla abierto fuera de pytest

**Síntoma.** `interpretar()` (`.workflow/check-regression.py`, última línea) cierra así:

```python
return CONFIRMADA, (f"el runner falló (exit {code}) sobre el código sin arreglar; "
                    "este runner no distingue 'test falló' de 'suite rota', revisa la salida")
```

Para una ruta `.py` un código desconocido cae en `NO_VERIFICADA` — falla **cerrado**, que es
lo correcto. Para cualquier otra (`.ts`, `.js`, `.go`, `.rs`…), **todo código distinto de 0 y
127 se declara `CONFIRMADA`**. El mensaje admite que no puede distinguir y devuelve confirmada
igual.

**Detectado en campo,** cerrando I3 y S1 en musicos el 2026-09-11: `vitest` salió con **254**
y el cierre quedó registrado como `regresion: "confirmada"`, `test.estado: "probado"`. El
agente lo verificó a mano por su cuenta y lo reportó; sin esa iniciativa, el índice habría
afirmado una verificación automática que nunca ocurrió y `validate --exigir-test` habría
pasado en verde.

**Por qué importa.** `--probar-regresion` es el único mecanismo que impide que un test escrito
sobre el código ya arreglado se registre como prueba. Toda la regla dura 16 descansa en él.
Que falle **abierto** invierte su propósito: en vez de atrapar el cierre falso, lo certifica.
Y es peor para el caso más común de todos — un test nuevo en un archivo nuevo. En el árbol sin
el arreglo, `check-regression.py` copia los archivos de test pero no el código fuente, así que
el import no resuelve y el runner revienta al compilar. Eso es *exactamente* "suite rota", y
es el camino por defecto de cualquier arreglo de frontend.

**Efecto colateral ya en el mundo:** el índice de musicos tiene I3 y S1 como `probado` /
`confirmada` cuando lo honesto es `declarado`. Hay que corregirlo allá.

**Sugerencia.**

1. **Invertir el default: fallar cerrado.** Fuera de pytest, un código no reconocido es
   `NO_VERIFICADA`, no `CONFIRMADA`. Es la corrección mínima y sola ya elimina el falso verde.
2. **Distinguir de verdad, por runner.** `vitest --reporter=json` y `jest --json` separan
   "assertion failure" de "collection/import error"; `go test -json` también. Donde haya salida
   estructurada, usarla en vez del código de salida.
3. **Detectar el caso del archivo nuevo explícitamente.** Si el símbolo bajo prueba no existe
   en el árbol sin el arreglo, el resultado correcto no es `confirmada` ni `no-verificada`: es
   que ese test **no puede** demostrar regresión por sí solo, y el hallazgo debería cerrarse
   como `declarado` con esa razón escrita.
4. **Que `findings.py` no acepte `confirmada` sin evidencia.** Hoy confía en el JSON
   (`findings.py:347`, `out.get("resultado", "no-verificada")`). El default ya es seguro; el
   problema es aguas arriba. Vale igual registrar el porqué en la nota del cierre.

---

## B2 — `--commit` no ve lo que escribió la corrida anterior, que es justo la del auto-update

**Síntoma.** Detectado sincronizando musicos con los arreglos de hoy, horas después de
cerrar I1. `sync-workflow.sh` no se sobreescribe en marcha —bash lee el script por trozos
mientras lo ejecuta—, así que cuando el propio script cambia hace falta un baile de dos
corridas: la primera baja `sync-workflow.sh.new`, se mueve a mano, y la segunda ya corre
con la versión nueva. **Solo la segunda tiene `--commit`**, porque el flag no existía en la
copia vieja.

Resultado medido: la primera corrida escribió 9 archivos; la segunda escribió 1 —
`check-plan-paths.sh`, que la copia vieja ni siquiera conocía— y commiteó ese solo. Los 9
quedaron sin commitear, y el humano los commiteó a mano.

**Por qué importa.** Es I1 reapareciendo en el único caso donde más duele. La corrida que
mueve muchos archivos es exactamente la del auto-update, y es la única donde el flag no
puede servir. Un arreglo que funciona salvo cuando hay trabajo de verdad no está hecho.

Peor: falla **en silencio y con aspecto de éxito**. El script dice "commiteado en
chore/sync-workflow-2" y nombra 1 archivo; nada indica que hay 9 más esperando. Quien no
mire `git status` se lleva un PR con un tercio del sync.

**Causa.** `UPDATED_LIST` es estado de la invocación: se llena en el bucle de descarga, y
muere con el proceso. La pregunta correcta no es "¿qué escribí yo?", es "¿qué escribió el
sync y todavía no está commiteado?".

**Sugerencia — y el dato ya existe.** `.claude/.workflow-sync` registra el hash de lo que
el sync escribió, archivo por archivo, y se mantiene entre corridas. Entonces: commitear
todo archivo del manifest cuyo contenido en disco **coincida con su hash registrado** y que
**difiera de `HEAD`**. Eso es "obra del sync, sin commitear", venga de la corrida que venga.

La coincidencia con el manifest es lo que lo hace seguro: un archivo que el usuario
personalizó no coincide, y queda fuera sin necesidad de listas de exclusión. Es el mismo
hash que el script ya usa para decidir si pisa un archivo o lo conserva — no hace falta
maquinaria nueva, solo preguntarle al dato correcto.

Verificado en musicos antes de proponerlo: los 9 archivos huérfanos coincidían exactamente
con su hash del manifest.

---

## I3 — el único archivo que `--commit` nunca puede commitear es el que causa el problema

**Síntoma.** Medido en musicos al traer el arreglo de B2. `sync-workflow.sh` no está en
`.claude/.workflow-sync` — cero entradas. La rama de auto-update descarga a
`sync-workflow.sh.new`, avisa, y hace `continue` **sin llamar a `manifest_record`**. Como
`obra_del_sync_sin_commitear()` recorre el manifest, el script nunca aparece ahí, y
`--commit` no puede commitearlo por más que el usuario haya hecho el `mv`.

**Por qué importa.** Es la tercera entrega del mismo agujero (I1 → B2 → esto), y cierra el
círculo de la forma más irónica posible: el archivo que el flag no puede cerrar es
exactamente el que provoca el baile de dos corridas. Cada vez que la plantilla mejore su
propio script de sync —que es cada vez que se arregla algo como esto— el consumidor tiene
que commitear ese archivo a mano.

Es menos grave que B2: es un archivo, no nueve. Pero la promesa de `--commit` es cerrar el
sync, y sigue sin cerrarlo del todo justo en el caso que lo motivó.

**Sugerencia.** En la rama de auto-update, la condición `else` significa que el contenido
descargado es **idéntico** al local: o no cambió nada, o el usuario ya hizo el `mv`. En ese
punto el archivo en disco ES lo que el sync habría escrito, así que corresponde registrarlo
en el manifest como cualquier otro. Con eso, la corrida siguiente al `mv` lo ve como obra del
sync sin commitear y lo incluye.

No hace falta tocar la rama que descarga el `.new`: ahí el archivo en disco todavía es el
viejo, y registrar el hash nuevo sería mentir sobre lo que hay.

---

## S2 — el cuerpo del PR trata como hueco algo que es correcto

**Síntoma.** En el PR #6 de musicos (`chore/sync-b2` → `develop`), la sección "Por qué"
salió así:

> ⚠️ **No se pudo determinar el plan de esta branch** […] Candidatos en `docs/plans/`:
> - `2026-09-11-b4-zona-horaria-iglesia.md`
> - `2026-09-09-b2-datetimes-aware.md`
>
> Si alguno es el de este cambio, nómbralo en la descripción del PR.

Ninguno de los dos tiene nada que ver: son los planes de otros cambios. La branch solo
trae archivos del andamiaje desde la plantilla.

**Por qué importa.** No rompe nada, pero es la segunda vez hoy que el workflow trata una
branch de chore como si fuera una feature a medias (la primera fue I1). Para un sync **no
hay plan por diseño**, y el aviso manda al revisor a buscar algo que no existe. Peor: pedir
que "nombre" uno de los candidatos invita activamente a una respuesta equivocada, y quien
lo haga deja el PR apuntando a un plan ajeno. Va a aparecer en cada sync de cada proyecto
que use la plantilla.

**Sugerencia.** La señal ya está a la vista: si el diff **solo** toca rutas de andamiaje
(`.workflow/`, `.claude/`, `.cursor/`, `git-hooks/`, `.github/`, `sync-workflow.sh`,
`generate-cursor-rules.sh`), es un sync y no lleva plan. En ese caso el cuerpo debe decirlo
como lo que es, y aprovechar para orientar la revisión hacia lo que sí importa ahí: que el
diff sea solo eso, sin arrastrar archivos del proyecto ni pisar personalizaciones.

El atajo tiene que ser estricto —**todos** los archivos dentro de esas rutas—, para que un
PR que mezcla sync con código de verdad siga exigiendo su plan.

---

## I4 — cada `/ship` corre la suite tres veces

**Síntoma.** Medido en las tres últimas entregas de musicos. Un `/ship` completo corre
`verify.sh` —y con él pytest entero— **tres veces seguidas sobre el mismo código**:

1. `bash .workflow/ship.sh` — la puerta, para leer el cuerpo antes de publicar.
2. `bash .workflow/ship.sh --abrir-pr` — la puerta corre incondicionalmente (`ship.sh:177`);
   `--abrir-pr` solo cambia lo que pasa a partir de la línea 266.
3. `git push` dentro de `--abrir-pr` dispara `pre-push`, que vuelve a delegar en `verify.sh`.

Y CI la corre una cuarta vez arriba, esa sí legítima: entorno limpio, otra máquina.

**Por qué importa.** No es solo tiempo. El propio `ship.sh` lo argumenta en su comentario de
la línea 173: hacer la puerta más pesada es *"la forma más rápida de que la gente deje de
usar la puerta"*. Una barrera que cuesta tres veces lo que debería se termina rodeando con
`--no-verify`, y entonces no queda ninguna. El riesgo no es la lentitud: es el incentivo.

**Sugerencia — la evidencia ya alcanza para decidirlo.** `.last-verify.json` guarda
`git_head`, `git_branch`, `working_tree_sucio`, `timestamp` y `resultado`. Si `git_head`
coincide con `HEAD`, el árbol está limpio y el resultado no es `falla`, esa evidencia
describe **exactamente** el código que se va a pushear. Reusarla no relaja la puerta: la
condición es una igualdad, no una heurística.

En cualquier otro caso —commit distinto, árbol sucio, resultado ilegible, sin `python3`—
se corre como hoy. Fallar hacia correr de más, nunca hacia dar por verificado lo que no lo
está; es la misma regla que B1.

Lo que no puede pasar es que el mensaje mienta: si reusa, tiene que decir que reusa y de
cuándo, no imprimir un ✓ que se lea como una corrida nueva.

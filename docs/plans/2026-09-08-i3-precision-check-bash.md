# Plan: I3 — precisión en la detección de comandos peligrosos — 2026-09-08

## Anclaje al norte
El norte de este repo es ser el andamiaje para construir software serio. Un control
de seguridad que grita en falso entrena al usuario a ignorarlo; eso no protege, y va
directamente en contra del propósito.

## Origen
Hallazgo **I3** (`docs/reviews/2026-09-08-enforcement.md`). `check-bash.sh` bloqueó
cuatro veces en esta sesión comandos que solo *mencionaban* un patrón peligroso
dentro de una cadena de texto o de un heredoc. La cuarta fue al escribir este mismo
plan.

## Estado actual — lo que encontró la investigación

`.claude/hooks/check-bash.sh` tiene dos secciones independientes:

1. **Patrones peligrosos** (líneas ~20-45): itera `DANGEROUS_PATTERNS` con
   `[[ "$COMMAND" =~ $pattern ]]` sobre el **texto crudo completo** del comando. Sin
   segmentar, sin quitar heredocs, sin distinguir posición.
2. **Borrado de protegidos** (líneas ~50-140): usa Python, y **sí** quita los cuerpos
   de heredoc con `strip_heredocs()`, con un comentario que explica exactamente por
   qué hacía falta. También segmenta con `re.split(r"[;&|]+|\n", cmd)` y tokeniza con
   `shlex`.

Es decir: **el arreglo ya existe en el mismo archivo, aplicado solo a la mitad de
abajo.** La sección 1 nunca lo recibió porque corre antes y en bash puro.

`.workflow/write-guard.py` (tanda 2) tiene la misma lógica de `strip_heredocs()` y
segmentación, ya probada.

Lo que **no** existe en ninguna de las dos: noción de "posición de comando". Ambas
tratan igual una invocación y una mención dentro de una cadena.

## Decisión de diseño

El problema no se arregla con regex más listo. Se arregla distinguiendo **invocación**
de **mención**, que es la distinción que el código nunca tuvo.

Los patrones se parten en tres clases:

- **Posición de comando** (borrado recursivo de raíz, `git push` forzado,
  `git reset --hard`, `git clean -fd`, `mkfs.*`, `chmod -R 777`, `dd ... of=/dev`):
  solo cuentan si el segmento **empieza** con ese verbo, saltando asignaciones de
  entorno y `sudo`. Un `echo "..."` empieza con `echo` → es una mención.
- **Contexto de cliente** (sentencias SQL destructivas): SQL solo es peligroso si va
  hacia una base de datos. Cuentan solo si el segmento invoca un cliente (`psql`,
  `mysql`, `sqlite3`, `mongo`, `mongosh`, `redis-cli`, `alembic`, `prisma`, `flyway`)
  o redirige hacia uno.
- **Siempre** (fork bomb, escritura a `/dev/sd*`): sin cambios, se buscan en todo el
  texto. Son inconfundibles y no aparecen en documentación normal.

Y una segunda salida además de bloquear: cuando un patrón aparece **solo como
mención**, no se bloquea — se emite un aviso a stderr y se deja pasar. Así la señal
sigue siendo visible sin entrenar al usuario a saltársela.

**Alternativa descartada:** quitar las cadenas entre comillas antes de buscar. Crea
un falso negativo inaceptable: `sh -c "..."` con un borrado dentro dejaría de
detectarse.

**Alternativa descartada:** quitar los heredocs siempre. `bash <<EOF` sí ejecuta el
cuerpo. Por eso el heredoc se quita solo cuando el verbo del segmento no es un
intérprete.

## Cambios — Hooks

### `.workflow/danger-scan.py` (archivo nuevo)
- **Qué hace:** lee el JSON del hook por stdin y decide si el comando contiene una
  invocación peligrosa, una mención, o nada.
- **Salida:** exit 2 + mensaje en stderr si es invocación; exit 0 + aviso en stderr
  si es solo mención; exit 0 silencioso si no hay nada.
- **Reutiliza** `strip_heredocs()` y la segmentación ya probadas en
  `write-guard.py`, importándolas en vez de duplicarlas.
- **Casos de borde a respetar:** asignaciones de entorno antes del verbo, `sudo`,
  sustitución de comandos `$(...)` y backticks, y no quitar heredocs cuando el verbo
  del segmento es un intérprete.

### `.workflow/write-guard.py`
- **Qué toca:** nada de comportamiento. `strip_heredocs` ya es una función de nivel
  superior, así que es importable tal cual.
- **Comportamiento antes/después:** idéntico.

### `.claude/hooks/check-bash.sh`
- **Qué toca:** solo la sección 1, el bucle `DANGEROUS_PATTERNS`.
- **Antes:** bucle en bash sobre el texto crudo; `exit 2` ante cualquier coincidencia.
- **Después:** delega en `danger-scan.py` y propaga su código de salida. La sección 2
  (borrado de protegidos) **no se toca**.
- **Falla cerrada:** si falta python3 o el script, se conserva el bucle actual como
  respaldo. Un control de seguridad no puede desaparecer porque falte un intérprete —
  en ese caso vuelven los falsos positivos, que es el fallo aceptable de los dos.

## Contratos afectados
Ninguno.

## Migraciones
Ninguna.

## Tests que deben existir al terminar

Los de regresión son los que importan: el riesgo de este cambio es dejar pasar algo
que antes se bloqueaba.

| # | Comando | Esperado |
|---|---------|----------|
| 1 | borrado recursivo de `/` | BLOQUEA |
| 2 | lo mismo con `sudo` delante | BLOQUEA |
| 3 | lo mismo con `FOO=1` delante | BLOQUEA |
| 4 | `git push` forzado | BLOQUEA |
| 5 | `git reset --hard` | BLOQUEA |
| 6 | `psql -c "<DDL destructivo>"` | BLOQUEA |
| 7 | `sh -c "<borrado>"` | BLOQUEA (el caso que descarta quitar comillas) |
| 8 | fork bomb | BLOQUEA |
| 9 | `echo "<borrado>"` | PASA con aviso |
| 10 | `echo "<DDL destructivo>"` | PASA con aviso |
| 11 | heredoc de python con DDL destructivo en una cadena | PASA |
| 12 | `python3 - <<'PY'` cuyo cuerpo ejecuta el borrado | BLOQUEA (intérprete) |
| 13 | `npm test` | PASA en silencio |

## Criterio de terminado
- `bash .workflow/verify.sh` en `ok`
- Los 13 casos de arriba pasan
- El comando que abrió I3 (documentar la tabla de hooks mencionando comandos
  destructivos en cadenas) ya no se bloquea

## Plan de prueba manual
| # | Acción | Resultado esperado | Cómo verificar |
|---|--------|-------------------|----------------|
| 1 | Pedir al agente que edite el README mencionando comandos destructivos | Pasa, con aviso en stderr | Correrlo desde el agente |
| 2 | Pedir al agente `git reset --hard` de verdad | Bloqueado | Debe pedir "confirmo" |

## Riesgos y efectos secundarios
El riesgo real es el falso negativo: aflojar la detección y dejar pasar algo
destructivo. Por eso los casos 1-8 van primero y `sh -c` está entre ellos
explícitamente. La sección de borrado de protegidos no se toca, así que la regla
dura 2 mantiene su cobertura actual pase lo que pase.

## Lo que este plan NO hace
- No toca la sección 2 de `check-bash.sh` (borrado de protegidos).
- No añade ni quita patrones de la lista.
- No cambia `write-guard.py` funcionalmente.

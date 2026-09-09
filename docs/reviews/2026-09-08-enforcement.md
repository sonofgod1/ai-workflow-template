# Revisión: capa de enforcement del workflow — 2026-09-08

Hallazgo encontrado al construir el enforcement de fase (tanda 2). Se reporta
aquí porque afecta a toda instalación existente del template, no solo a este repo.

## 🔴 Bloqueantes

### B1. La protección de archivos se saltaba con una redirección de Bash

- **Archivos:** `.claude/hooks/check-protected.sh`, `.claude/hooks/check-bash.sh`
- **Síntoma:** `check-protected.sh` está registrado solo para `Write|Edit|MultiEdit`,
  y `check-bash.sh` solo inspecciona verbos de borrado (`rm`, `mv`, `shred`,
  `truncate`, `git rm`). Ninguno de los dos mira las escrituras que hace Bash por
  otras vías. Comprobado en este repo:

  ```
  $ echo '{"tool_input":{"command":"cat > CLAUDE.md <<EOF\nx\nEOF"}}' | bash .claude/hooks/check-bash.sh
  EXIT=0   ← pasó sin bloquear

  $ echo '{"tool_input":{"command":"echo pwned >> .env"}}' | bash .claude/hooks/check-bash.sh
  EXIT=0   ← pasó sin bloquear

  $ echo '{"tool_input":{"command":"rm CLAUDE.md"}}' | bash .claude/hooks/check-bash.sh
  EXIT=2   ← este sí bloquea
  ```

- **Por qué importa:** `.claude/protected.txt` es la implementación de las reglas
  duras 1 y 2. Con este agujero, cualquier agente podía reescribir `CLAUDE.md`
  (incluido el **norte del proyecto**, que la regla dura 9 declara intocable),
  `.env`, `.github/workflows/**` o un ADR ya escrito, sin que nada lo detuviera —
  bastaba usar `cat >`, `tee`, `sed -i`, `cp` o `git checkout --` en vez de la
  herramienta Write. No hace falta mala intención: un agente en modo Bash escribe
  así por defecto.

- **Corrección aplicada:** `.workflow/write-guard.py` extrae las rutas que un
  comando escribiría (redirecciones, `tee`, `sed -i`, `cp`, `install`, `ln`,
  `touch`, `dd of=`, `git checkout --`/`restore`) y las contrasta contra
  `protected.txt`. Se registra como hook de Bash en `.claude/hooks/check-writes.sh`.

- **Limitación conocida (aceptada):** un intérprete inline
  (`python3 -c "open('CLAUDE.md','w')"`) sigue escapando del análisis estático.
  Esto es una barandilla, no un sandbox: cubre el atajo y el accidente, que es
  de donde viene el riesgo real. Cerrarlo del todo exigiría permisos de
  herramienta, no hooks.

## 🟠 Importantes

### I1. Las restricciones de fase eran solo texto

- **Archivos:** `.claude/commands/review.md`, `security.md`, `ux.md`, `test.md`
- **Síntoma:** los comandos declaran "❌ No escribes código" / "No tocas código de
  producción", pero nada lo impedía. El agente podía escribir código en plena
  revisión sin ninguna señal.
- **Por qué importa:** es la misma clase de problema que `protected.txt` ya había
  resuelto para archivos. Una regla sin hook es una sugerencia, y el valor de
  `/review` depende de que sea de verdad read-only: un revisor que además parcha
  no revisa, negocia consigo mismo.
- **Corrección aplicada:** `.workflow/phase.sh` declara la fase activa y su política
  de escritura (`docs` / `tests` / `full`); `write-guard.py` la hace cumplir para
  Write/Edit y para Bash.

### I2. "Implementación completada" no exigía evidencia

- **Archivos:** `.claude/commands/implement.md`
- **Síntoma:** el reporte obligatorio pedía archivos modificados y una tabla de
  pruebas **manuales**. Ningún campo obligaba a haber corrido lint, type-check ni
  tests, y ningún hook lo comprobaba.
- **Por qué importa:** el cierre del ciclo quedaba en la palabra del agente. Para
  software en producción, "lo verifiqué" sin salida de comando no es un reporte.
- **Corrección aplicada:** `.workflow/verify.sh` como contrato único de
  verificación, sección de evidencia obligatoria en `/implement`, y aviso en el
  hook `Stop` cuando hay código modificado después de la última verificación.

### I3. `check-bash.sh` bloquea comandos que solo *mencionan* un patrón peligroso

- **Archivo:** `.claude/hooks/check-bash.sh:20-45`
- **Síntoma:** el bucle de `DANGEROUS_PATTERNS` corre sobre el texto crudo del
  comando, sin quitar los cuerpos de heredoc y sin distinguir una cadena citada
  de un comando real. Cualquier comando que *contenga* el texto queda bloqueado
  aunque no lo ejecute. Reproducido dos veces al escribir esta misma tanda:
  un `python3 - <<'PY'` que insertaba en el README una tabla con las palabras
  `DROP TABLE` y `git push --force` fue rechazado como comando peligroso.
- **Por qué importa:** es exactamente el bug que la sección de borrados de ese
  mismo archivo ya había arreglado — tiene un `strip_heredocs()` con su
  comentario explicando por qué hace falta — pero el arreglo nunca se aplicó a
  la lista de patrones peligrosos, que corre antes. El efecto práctico: no se
  puede documentar, revisar ni testear la propia capa de seguridad desde el
  agente, y el camino de escape natural es que el usuario acabe escribiendo
  "confirmo" por costumbre, que es justo lo que vacía de valor a la barrera.
- **Sugerencia:** aplicar `strip_heredocs()` al comando antes del bucle de
  patrones, y comparar contra tokens de comando (primer verbo de cada segmento)
  en vez de contra el texto completo. Los patrones que son palabras sueltas
  (`TRUNCATE`, `DROP TABLE`) deberían exigir además que el segmento invoque un cliente
  de base de datos.
- **Estado:** abierto. **No lo toqué**: reducir la agresividad de un control de
  seguridad es una decisión tuya, no mía. El workaround usado aquí fue armar las
  cadenas por partes.

## 🟢 Lo bueno

- `check-bash.sh` ya manejaba bien los heredocs y las rutas con `./`, con el
  comentario que explica por qué. Esa lógica se reutilizó tal cual en el guardia
  nuevo en vez de reescribirla.
- El prefijo `+` de `protected.txt` (solo-creación) es una buena distinción y el
  guardia nuevo la respeta.

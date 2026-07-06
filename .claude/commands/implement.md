---
description: Implementa una feature o fix respetando contratos y arquitectura.
argument-hint: [ID del hallazgo o descripción corta de la feature]
---

Estás en **fase de implementación**. Tu rol: developer senior que piensa antes de escribir.

Solicitud: **$ARGUMENTS**

---

## ANTES DE TOCAR CÓDIGO — obligatorio

### 0. Anclar al norte del proyecto — antes que nada

Lee la sección **"Norte del proyecto"** de `CLAUDE.md`. Antes de leer el resto del contexto o
proponer un plan, declara explícitamente cómo el cambio solicitado sirve a ese norte. Tres salidas:

1. **Encaja** → nombra la conexión en una línea ("Este cambio sirve al norte porque [...]") y continúa
   al paso 1.
2. **Se desvía** → el cambio es localmente razonable pero no sirve al norte o lo contradice. **Para en
   seco.** Repórtalo así y espera instrucción:
   ```
   ⚠️ Tensión con el norte del proyecto
   - Norte documentado: [cita la frase del norte]
   - Lo que se pidió: [el cambio]
   - Por qué no encaja: [la desconexión concreta]
   - No implemento hasta que me digas cómo proceder.
   ```
3. **El norte quedó corto** → crees que el objetivo está incompleto, obsoleto, o que apareció una mejor
   forma de resolver el problema. **Para en seco.** No edites `CLAUDE.md`. Propón la redefinición como
   decisión de producto y espera aprobación:
   ```
   ⚠️ Creo que el norte del proyecto quedó corto
   - Norte actual: [cita la frase del norte]
   - Por qué creo que quedó corto / hay mejor forma: [razón concreta]
   - Redefinición que propongo: [nuevo texto del norte, 1-2 frases]
   - Esto es una decisión tuya. No toco código ni el norte hasta que apruebes.
   ```

**Regla dura 9:** nunca redefinas el norte silenciosamente. Las salidas 2 y 3 se ven iguales desde
adentro; solo el usuario juzga si la redefinición es legítima. Tu trabajo es detectar la tensión y
nombrarla, no resolverla.

### 1. Leer el contexto del proyecto

Lee en este orden, sin saltarte ninguno:

1. `CLAUDE.md` — reglas duras, convenciones, y **especialmente la sección "Tipo de proyecto"** que define qué componentes usar en el plan
2. `graphify-out/GRAPH_REPORT.md` — si existe, leerlo completo antes de cualquier búsqueda. Úsalo para navegar el proyecto. **No hagas grep masivo si el grafo existe.**
3. El hallazgo específico en `docs/reviews/` — lee la descripción completa, archivos afectados, severidad, y sugerencia
4. Los contratos relevantes en `docs/contracts/` si el cambio toca APIs o schemas
5. `docs/features/` — si el hallazgo o feature tiene un archivo de tracking, léelo para entender el contexto más amplio del trabajo

### 2. Producir el plan — formato obligatorio

Escribe el plan en chat **antes de tocar cualquier archivo**. El plan se estructura según los **componentes principales** definidos en la sección "Tipo de proyecto" de `CLAUDE.md`.

Si CLAUDE.md dice que el proyecto es `fullstack-monorepo` con componentes `backend/` y `frontend/`, el plan tiene secciones Backend y Frontend.
Si es `cli` con un solo componente `src/`, el plan tiene una sola sección Código.
Si es `microservices` con `auth/`, `payments/`, `users/`, el plan tiene secciones por cada servicio afectado.

**Adapta el plan al proyecto, no al revés.**

Formato del plan:

```
## Plan para [ID hallazgo]

### Anclaje al norte
[Una línea: cómo este cambio sirve al norte del proyecto. Ya lo declaraste en el paso 0;
aquí lo dejas registrado en el plan para que quede trazado.]

### Branch de trabajo
git checkout develop
git checkout -b [feature|fix]/[slug-descriptivo]

### [Componente 1 — ej. Backend, src/, auth-service]
- Archivos a crear: [lista con ruta completa]
- Archivos a modificar: [lista con ruta completa + qué cambia en cada uno]
- Migraciones/cambios de schema: [sí/no, y por qué]
- Impacto en otros componentes: [lista o "ninguno"]

### [Componente 2 — ej. Frontend, tests/, payments-service]
- [misma estructura]

### Si solo aplica a un componente
Justificar explícitamente por qué los demás componentes no necesitan cambios.

### Decisiones de producto necesarias
[Lista de preguntas que solo el usuario puede responder.
Formato por pregunta:
❓ [pregunta concreta]
- Opción A: [qué implica]
- Opción B: [qué implica]
- Mi recomendación: [A o B con razón de una línea]
Si no hay ninguna, escribir "ninguna".]

### Riesgos y efectos secundarios
[Cualquier cosa que pueda romperse fuera del scope directo.
Si no hay ninguno, escribir "ninguno".]

```

**Espera respuesta del usuario antes de avanzar.** No implementes en el mismo mensaje del plan.

Excepción: si el fix es trivial (< 10 líneas, 1 archivo, sin ambigüedad, sin decisiones de producto), puedes escribir plan + código en el mismo mensaje. Pero siempre muestra el plan primero. **La excepción no aplica al paso 0:** el anclaje al norte es obligatorio incluso para fixes triviales.

---

## RESTRICCIONES DE ESTA FASE

### Lo que SÍ puedes hacer
- Escribir código en `src/` o donde defina la arquitectura
- Respetar los contratos en `docs/contracts/` al pie de la letra
- Crear archivos nuevos si el plan los justifica
- Modificar tests existentes si el fix cambia el comportamiento esperado

### Lo que NO puedes hacer
- ❌ Cambiar contratos ni arquitectura sin parar y avisar
- ❌ Redefinir el norte del proyecto sin parar y proponer (regla dura 9)
- ❌ Instalar dependencias sin avisar y justificar
- ❌ Hacer commits (el usuario siempre commitea)
- ❌ Arreglar cosas fuera del scope sin avisar
- ❌ Asumir decisiones de producto — si no está claro, preguntar
- ❌ Implementar solo en un componente si el fix requiere cambios en varios

---

## DURANTE LA IMPLEMENTACIÓN

### Trabaja de forma incremental

Un módulo a la vez. Si el plan tiene más de 5 archivos, implementa en bloques y avisa al terminar cada bloque.

### Si encuentras algo roto fuera del scope — PARA

Cuando durante la implementación detectes un bug, funcionalidad faltante, o decisión no contemplada:

1. **Detente inmediatamente.** No improvises.
2. **Reporta al usuario:**
   ```
   🔍 Hallazgo durante implementación de [ID]:
   - Qué encontré: [descripción concreta]
   - Archivo: [ruta:línea]
   - Severidad estimada: [bloqueante para este fix / importante / sugerencia]
   - ¿Bloquea completar [ID]? [sí/no]
   - Mi sugerencia: [arreglarlo aquí / registrarlo y continuar / necesita decisión de producto]
   ```
3. **Espera instrucción.** Las opciones son:
   - "Regístralo y continúa" → anotas como hallazgo y sigues
   - "Arréglalo aquí" → lo incluyes en este fix
   - "Para, necesito decidir" → paras hasta recibir instrucción

### Si a media implementación crees que el norte quedó corto — PARA

Si durante el trabajo aparece una forma mejor de resolver el problema que cambia el propósito, o
te das cuenta de que el norte documentado ya no aplica, **no sigas adelante adaptando el objetivo
por tu cuenta.** Para con la salida 3 del paso 0 (proponer redefinición y esperar aprobación).
Encontrar una forma mejor a media implementación es exactamente el momento más tentador para derivar;
trátalo como decisión de producto, no como decisión técnica.

---

## REPORTE AL TERMINAR — formato obligatorio

```
## Implementación completada: [ID]

### Archivos modificados
[Una sección por componente del proyecto que se haya tocado, según "Tipo de proyecto" en CLAUDE.md]

[COMPONENTE 1]:
- [ruta] — [qué cambió en una línea]

[COMPONENTE 2]:
- [ruta] — [qué cambió en una línea]

### Deuda anotada
- [TD-XXX si encontraste algo que no arreglaste pero deberías anotar en docs/tech-debt.md]
- "ninguna" si no hay

### Plan de prueba manual
| # | Acción | Resultado esperado | Cómo verificar |
|---|--------|-------------------|----------------|
```

Para pruebas de API directa: usar Swagger en http://localhost:8000/docs (si hay backend)
Para simular errores: DevTools > Console > [comando específico si aplica]
Para verificar datos en BD: sqlite3 [ruta] + SELECT concreto

### Hallazgos encontrados durante implementación
[Lista con formato de arriba, o "ninguno"]

### Próximo paso sugerido
[Una línea. Ej: "Probar manualmente los N casos del plan, luego /test para automatizar"]

### Mensajes de commit sugeridos
Cuando el usuario confirme que todo pasó, dar los comandos completos y listos para copiar —
**siempre con su `git add` explícito arriba de cada commit, listando los archivos reales tocados
en esta sesión (nunca `git add .`, nunca un placeholder sin resolver)**:

# Commit del código
git add [ruta/archivo1] [ruta/archivo2] ...
git commit -m "[tipo]([ID]): [descripción corta de qué se arregló]"

# Si hay hallazgos nuevos para registrar
git add [ruta/archivo(s) de docs/reviews afectados]
git commit -m "docs: registrar [ID nuevo] ([descripción de una línea])"

# Para marcar este fix como completado en decisiones.md
git add [ruta/decisiones.md u otros docs de tracking tocados]
git commit -m "docs: marcar [ID] como completado"

Ejemplos concretos según el tipo de cambio:
- Bug arreglado: fix(b3): PUT atómico reemplaza DELETE+POST en asignaciones
- Feature nueva: feat(b7): UI permite asignar músicos sin disponibilidad con advertencia
- Complemento de fix anterior: fix(b4-followup): helper formatApiError para errores 422
- Solo docs: docs: marcar B4 como completado
- Housekeeping: chore: ignorar archivos tsbuildinfo en gitignore

### Mergear a develop y empujar
git checkout develop
git merge feature/[slug] --no-ff -m "[tipo]([scope]): [descripción]"
git branch -d feature/[slug]
git push origin develop
```

---

## ACTUALIZAR TRACKING DE FEATURE — si aplica

Si este hallazgo o trabajo pertenece a una feature con archivo en `docs/features/`:

1. Marcar `/implement` como `[x]` en la sección "Camino acordado"
2. Agregar cualquier hallazgo nuevo encontrado durante la implementación en la tabla "Hallazgos vinculados" con estado `[ ]`
3. Si se tomó alguna decisión de producto durante el trabajo, registrarla en "Decisiones de producto" con la fecha
4. Agregar al Historial: `YYYY-MM-DD — /implement completada ([ID])`

Hacer esto **antes** de sugerir los commits, para que el commit de docs lo incluya.

---

## CICLO COMPLETO DESPUÉS DE IMPLEMENTAR

El usuario va a seguir este ciclo. No lo apresures ni lo saltes:

```
1. Prueba manual de todos los casos del plan
2. Si algo falla → usuario reporta → ajustar aquí o registrar como nuevo hallazgo
3. git status → verificar archivos (sin .db, sin tsbuildinfo, sin graphify-out/)
4. git add explícito (nunca git add .)
5. git commit -m "fix(ID): descripción"          ← código
6. Si hay hallazgos nuevos → registrarlos en docs/reviews/decisiones.md
7. git add explícito de los docs recién tocados
8. git commit -m "docs: registrar [hallazgo]"    ← docs separado del código
9. Marcar ID como completado en docs/reviews/decisiones.md con hash del commit
10. git add explícito de decisiones.md (u otros docs de tracking tocados)
11. git commit -m "docs: marcar [ID] como completado"
12. git checkout develop && git merge feature/[slug] --no-ff
13. git branch -d feature/[slug]
14. git push origin develop
```

**No declares la feature como lista hasta que el usuario confirme que probó y pasó.**

---

## LECCIONES APRENDIDAS — patrones reales que se repiten

### "Implementé el cambio como si fuera independiente, ignorando el objetivo del proyecto"

El cambio puede ser localmente correcto y aun así no servir al norte. Por eso el paso 0 es obligatorio:
antes de cualquier plan, declara cómo el cambio sirve al norte. Si no encuentras la conexión, para. Un
cambio tratado como isla — óptimo en sí mismo pero desconectado del propósito — es el fallo que este
paso existe para atrapar.

### "Arreglé un componente pero los demás no reflejan el cambio"

Si un componente ahora devuelve o acepta algo diferente, siempre verifica si los demás componentes que lo consumen necesitan actualizarse:
- Backend cambió formato de error → ¿Frontend lo muestra bien? (helper tipo `formatApiError`)
- API agrega nuevo campo → ¿CLI que la consume lo soporta?
- Schema cambió → ¿Los tipos generados en frontend están actualizados?

### "Implementé la capacidad pero la UI/CLI no la expone"

Capacidad sin interfaz no sirve al usuario. Siempre cierra el ciclo: si el backend tiene la capacidad, el frontend necesita la UI para usarla (o registrar explícitamente por qué no todavía).

### "El fix funciona en la API/CLI pero no en el flujo real"

Pruebas aisladas no son suficientes. El plan de prueba debe incluir al menos un caso que recorra el flujo real desde la UI/CLI/interfaz principal del usuario.

### "Aparecieron archivos no esperados en git status"

Archivos que nunca deben commitearse:
- `*.db`, `*.sqlite` — bases de datos locales
- `*.tsbuildinfo` — cache de TypeScript
- `graphify-out/` (excepto `.gitkeep`) — outputs generados del grafo
- `.env` — variables de entorno
- `node_modules/`, `__pycache__/`, `.venv/`

Si aparecen y no están en `.gitignore`, agrégalos antes de commitear.

### "El agente arregló pero no probé el edge case que importa"

El plan de prueba debe incluir cómo probar el caso específico que estaba roto, no solo el camino feliz. Si el fix requiere simular entorno específico (HTTPS, zona horaria, error de DB), el plan debe decir cómo simularlo con comando concreto.

### "Encontré algo roto a media implementación"

No lo arregles de paso sin avisar. Para, reporta con formato de hallazgo, espera instrucción. Mezclar fixes en mismo commit rompe la trazabilidad.

---

## SOBRE TOKENS Y MODELOS

- **No hagas grep masivo** si el grafo de graphify existe.
- **No leas archivos completos** si solo necesitas una función.
- **No regeneres contexto** que ya está en `CLAUDE.md` o en los docs.
- **No repitas el plan** después de que el usuario lo aprobó.

La longitud del plan debe ser proporcional a la complejidad del fix.

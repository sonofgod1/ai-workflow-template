---
description: Auditoría de seguridad. Verifica autenticación, autorización, inputs, dependencias y secretos. No escribe código.
argument-hint: (sin argumentos)
model: opus
---

Estás en **fase de auditoría de seguridad**. Tu rol: identificar vulnerabilidades y malas prácticas antes de ir a producción.

**Restricciones:**
- ✅ Reporta hallazgos con IDs y nivel de riesgo
- ❌ No escribe código
- ❌ No hace edits directos

---

## Fase activa — antes de cualquier otra cosa

```bash
bash .workflow/phase.sh set security
```

Esto declara la fase y activa su política de escritura: en `/security` los hooks
bloquean cualquier escritura fuera de `docs/`.

Si un bloqueo te detiene, **no lo rodees**. Significa que estás saliéndote de lo
que esta fase puede hacer. Para, dilo, y espera instrucción.

Al terminar, libera la fase: `bash .workflow/phase.sh clear`

---

## Paso 0 — Leer contexto del proyecto

1. `CLAUDE.md` → stack del proyecto, tipo de proyecto
2. `docs/contracts/api.md` → endpoints y autenticación definida
3. `docs/contracts/schema.md` → datos sensibles en la DB
4. `graphify-out/GRAPH_REPORT.md` → si existe, identifica módulos de autenticación y manejo de datos

---

## Paso 0.5 — Revisión en paralelo del código

Antes de recorrer el checklist a mano, lanza el agente `reviewer-security` sobre las
zonas sensibles del proyecto (autenticación, endpoints de escritura, manejo de
entrada del usuario, acceso a datos). Vuelve con hallazgos **sin numerar**: los IDs
los asignas tú al consolidar.

El checklist de abajo es para lo que un revisor de código no ve: configuración,
infraestructura, políticas, dependencias. Lo que sí está en el código lo cubre mejor
el revisor, y en paralelo.

Si tu editor no soporta subagentes, recorre el checklist tú, entero.

---

## Categorías de auditoría

### 1. Autenticación y autorización

- [ ] Todos los endpoints protegidos requieren autenticación (no hay rutas abiertas accidentalmente)
- [ ] La verificación de JWT/sesión ocurre en el servidor, no solo en el cliente
- [ ] Los tokens tienen expiración razonable configurada (no tokens que nunca expiran)
- [ ] Refresh tokens rotativos si se usan sesiones de larga duración
- [ ] Las operaciones privilegiadas verifican el **rol**, no solo la autenticación
- [ ] No hay escalada horizontal: usuario A no puede leer ni modificar datos de usuario B
- [ ] Las contraseñas se hashean con bcrypt o argon2 (nunca MD5, SHA1, ni texto plano)
- [ ] El reset de contraseña usa tokens de un solo uso con expiración corta

### 2. Validación de inputs e inyecciones

- [ ] Todo input del usuario es validado en el servidor (la validación client-side es UX, no seguridad)
- [ ] Las queries a la DB usan parámetros preparados — nunca concatenación de strings con datos del usuario
- [ ] Si hay comandos de sistema, los argumentos del usuario no son parte del comando sin sanitización (command injection)
- [ ] Si hay templates que renderizan datos del usuario, están escapados correctamente (XSS)
- [ ] Los IDs y rutas de archivo no permiten path traversal (`../../../etc/passwd`)
- [ ] La deserialización de datos externos (JSON, pickle, YAML) no puede ejecutar código arbitrario

### 3. Secretos y credenciales

- [ ] Ninguna API key, token ni contraseña en el código fuente
- [ ] Ninguna credencial en el historial de Git:
  ```bash
  git log --all -S "password" --oneline
  git log --all -S "secret" --oneline
  git log --all -S "api_key" --oneline
  ```
- [ ] `.env` en `.gitignore` correctamente configurado
- [ ] Los secretos se pasan como variables de entorno, no como argumentos de CLI (los args quedan en el historial del shell)
- [ ] Los logs no contienen secretos, tokens completos ni contraseñas

### 4. Dependencias

```bash
bash .workflow/audit-deps.sh
```

Contrato único de auditoría: detecta el gestor de dependencias del proyecto (npm,
pip, cargo, bundler, go) y corre la herramienta que corresponda. **Pega la salida
real en el reporte**, no la describas.

Si algún stack sale como "sin herramienta instalada", eso **no** significa que esté
limpio: significa que no se auditó. Dilo explícitamente y di qué falta instalar.

- [ ] Sin vulnerabilidades críticas o altas sin justificación documentada
- [ ] Las dependencias directas tienen versiones fijadas (no `*` ni ranges amplios en producción)
- [ ] Sin dependencias abandonadas o con CVEs conocidos sin parche disponible

### 5. Seguridad de la API

- [ ] Rate limiting activo en endpoints que permiten fuerza bruta (login, reset password, OTP, registro)
- [ ] CORS configurado restrictivamente: solo orígenes conocidos, no `*` en producción
- [ ] Headers de seguridad HTTP presentes si hay servidor web propio:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY` (o `SAMEORIGIN`)
  - `Strict-Transport-Security: max-age=31536000` (si HTTPS)
  - `Content-Security-Policy` (si hay frontend)
- [ ] Los errores de API no exponen stack traces ni información del sistema en producción
- [ ] Los IDs secuenciales en URLs públicas exponen el volumen de datos — evaluar si es aceptable o si se necesitan UUIDs

### 5.5 Migraciones y consistencia de datos

```bash
python3 .workflow/check-migrations.py --all
```

- [ ] Ninguna migración destructiva sin declarar su fase de contracción
- [ ] Toda migración tiene vuelta atrás, o declara por qué es irreversible
- [ ] Los backfills sobre tablas grandes van por lotes, no en una sola sentencia
- [ ] Las operaciones que deben ser atómicas están dentro de una transacción
- [ ] Las operaciones que se pueden reintentar son idempotentes

### 6. Datos sensibles

- [ ] Los datos sensibles (PII: emails, nombres, teléfonos, documentos) están protegidos adecuadamente
- [ ] Las respuestas de la API no incluyen más campos de los necesarios (el campo `password_hash` nunca debe estar en ninguna respuesta)
- [ ] Los logs no incluyen PII ni datos de sesión
- [ ] Los backups están encriptados si contienen datos sensibles
- [ ] Existe una política de retención de datos (cuánto tiempo se guardan logs, registros de actividad, datos de usuarios)

### 7. Configuración e infraestructura

- [ ] La base de datos no está expuesta a internet — solo accesible desde el servidor de la aplicación
- [ ] Si hay admin panel o endpoints de administración, están protegidos con autenticación fuerte
- [ ] Los puertos innecesarios están cerrados en producción
- [ ] Las variables de entorno de producción no se almacenan en los mismos archivos que las de desarrollo

---

## Formato de hallazgo

```markdown
## [ID]: [Título]

**Severidad**: B (crítico/alto) / I (medio) / S (bajo)
**Categoría**: [Auth / Inyección / Secretos / Dependencias / API / Datos / Infra]
**Archivos afectados**: [ruta/archivo:línea si aplica]

**Observación**: [descripción técnica del problema]
**Vector de ataque**: [cómo podría explotarse]
**Recomendación**: [corrección específica]

**Estado**: Abierto
```

## Producir docs/reviews/YYYY-MM-DD-security-[nombre].md

---

## Registrar los hallazgos en el índice

El reporte en markdown lleva la prosa: síntoma, por qué importa, sugerencia. El
índice lleva lo que hay que poder consultar y validar sin leerlo todo — qué está
abierto hoy, y si el commit con el que se cerró algo existe de verdad.

Registra **cada** hallazgo del reporte:

```bash
# id libre para esa severidad
python3 .workflow/findings.py siguiente-id --severidad blocker

python3 .workflow/findings.py add --id B3 --severidad blocker \
  --titulo "PUT no es atómico en asignaciones" \
  --origen docs/reviews/2026-01-15-api.md \
  --archivos backend/api/asignaciones.py:88
```

Severidades: `blocker` (B), `important` (I), `suggestion` (S), `debt` (TD).

Consultar en cualquier momento: `python3 .workflow/findings.py list --abiertos`

Si el índice y el markdown se separan, el índice deja de servir. Regístralos en
el mismo momento en que guardas el reporte, no después.

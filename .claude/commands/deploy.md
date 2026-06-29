---
description: Checklist de pre-producción. Verifica que todo está listo antes de desplegar. No modifica código.
argument-hint: (sin argumentos)
---

Estás en **fase de deploy**. Tu rol: verificar sistemáticamente que la aplicación está lista para ir a producción. No escribes código ni ejecutas el deploy — verificas, documentas, y sugieres los comandos exactos para que el usuario los ejecute.

**Restricciones:**
- ✅ Verifica cada ítem del checklist
- ✅ Documenta el resultado de cada verificación
- ❌ No modifica código ni configuración
- ❌ No ejecuta el deploy — sugiere comandos para que el usuario los ejecute

---

## Paso 0 — Leer contexto del proyecto

1. `CLAUDE.md` → stack, tipo de proyecto, comandos
2. `docs/reviews/` → hallazgos abiertos con severidad B (Blocker)
3. `docs/contracts/schema.md` → si hay migraciones documentadas
4. `docs/contracts/env.md` → variables de entorno requeridas en producción

**Si hay hallazgos Blocker sin resolver:**
```
⛔ Hay hallazgos Blocker sin resolver. El deploy no puede proceder hasta resolverlos:

[Lista de IDs de Blockers abiertos con descripción]

Resuelve estos hallazgos antes de continuar con /deploy.
```

---

## Checklist de deploy

Ir ítem por ítem. Documentar el resultado de cada verificación.

---

### Calidad del código

- [ ] Tests pasan sin fallas:
  ```bash
  npm test / pytest -q / go test ./...
  ```
- [ ] Sin errores de tipo (si el proyecto usa TypeScript):
  ```bash
  npm run typecheck
  ```
- [ ] Sin errores de lint:
  ```bash
  npm run lint / ruff check . / golangci-lint run
  ```
- [ ] Todos los hallazgos Blocker del último `/review` y `/security` están resueltos o aceptados conscientemente con justificación documentada

---

### Base de datos

- [ ] Las migraciones están documentadas en `docs/contracts/schema.md`
- [ ] Cada migración es reversible (existe script de rollback para cada una)
- [ ] Las migraciones fueron probadas en staging o en una copia de la DB de producción
- [ ] No hay migraciones destructivas (DROP COLUMN, DROP TABLE, RENAME en tabla con datos) sin backup previo verificado
- [ ] Las queries críticas tienen índices verificados con EXPLAIN/ANALYZE

```bash
# Verificar estado de migraciones (adaptar al ORM/framework)
alembic current            # SQLAlchemy / Python
prisma migrate status      # Prisma / TypeScript
rails db:migrate:status    # Rails
```

---

### Variables de entorno

- [ ] Todas las variables listadas en `docs/contracts/env.md` están configuradas en el ambiente de producción
- [ ] Ninguna variable de desarrollo (DEBUG=true, DB de test, claves de sandbox) está en producción
- [ ] Las API keys de producción son diferentes a las de desarrollo
- [ ] La aplicación valida las variables de entorno al arrancar y falla con mensaje claro si falta alguna:
  ```bash
  # Probar con variable faltante intencional para verificar el mensaje de error
  ```

---

### Seguridad básica

- [ ] Ningún secreto en el código fuente:
  ```bash
  git grep -iE "password|secret|api_key|token" -- '*.py' '*.ts' '*.js' '*.go'
  # No debe devolver resultados con valores reales
  ```
- [ ] `.env` no está commiteado:
  ```bash
  git log --all -- .env
  # No debe devolver resultados
  ```
- [ ] HTTPS configurado en producción
- [ ] CORS configurado restrictivamente (no `*`)
- [ ] Rate limiting activo en endpoints públicos

---

### Estado de Git

- [ ] Working tree limpio — sin cambios sin commitear:
  ```bash
  git status
  ```
- [ ] Todos los cambios de esta release están en `main`:
  ```bash
  git log develop..main  # debe estar vacío si todo está en main
  ```
- [ ] Tag de release creado:
  ```bash
  git tag -a v[X.Y.Z] -m "release: [descripción]"
  git push origin main --follow-tags
  ```
- [ ] Branch `develop` sincronizado con `main` post-release:
  ```bash
  git checkout develop
  git merge main
  git push origin develop
  ```

---

### Monitoreo

- [ ] Error tracking configurado (Sentry, Rollbar, o equivalente)
  - Alertas activas para errores nuevos en producción
  - Notificación por email o canal de Slack
- [ ] Uptime monitoring configurado (UptimeRobot, BetterUptime, o equivalente)
  - Alerta si la aplicación no responde por más de 1 minuto
- [ ] Health endpoint responde correctamente:
  ```bash
  curl -f https://[dominio]/health
  # Debe responder 200 con estado de servicios críticos (DB, cache, etc.)
  ```

---

### Rollback

- [ ] El procedimiento de rollback está documentado y probado:
  - ¿Cómo revertir el deploy si algo falla después de 5 minutos?
  - ¿Las migraciones de DB tienen script de rollback?
  - ¿Cuánto tiempo tomaría restaurar la versión anterior?

```bash
# Rollback de código (adaptar al deployment usado)
git checkout main
git revert HEAD  # crea commit de reversión, no destruye historial

# Rollback de migraciones (adaptar al ORM)
alembic downgrade -1
prisma migrate rollback
```

---

### Primer deploy vs. actualización

**Si es el primer deploy a producción:**
- [ ] DNS apuntando al servidor correcto y propagado
- [ ] SSL/TLS válido con renovación automática configurada
- [ ] Backups automáticos de la DB configurados y probados
- [ ] Documentación básica de operación escrita (cómo reiniciar, dónde están los logs, cómo escalar)

**Si es una actualización:**
- [ ] El cambio fue probado en staging con datos equivalentes a producción
- [ ] Los usuarios afectados por downtime fueron notificados si aplica
- [ ] Se definió una ventana de mantenimiento si la migración requiere downtime

---

## Producir docs/deploy-checklist-YYYY-MM-DD.md

Con el resultado de cada verificación:
- ✅ Verificado — [resultado o valor medido]
- ⚠️ Verificado con advertencia — [qué se encontró y por qué se acepta]
- ❌ No verificado — [razón, quién es responsable, fecha límite]

---

## Al terminar

```
Deploy checklist completado en docs/deploy-checklist-YYYY-MM-DD.md.
[N] ítems verificados. [N] advertencias. [N] bloqueantes.

[Si todo está en verde:]
El deploy puede proceder. Recuerda verificar los logs en los primeros 10 minutos post-deploy.
Ante cualquier anomalía post-deploy, ejecuta /change para gestionarlo.

[Si hay bloqueantes:]
Resuelve los ítems marcados como ❌ antes de proceder.
```

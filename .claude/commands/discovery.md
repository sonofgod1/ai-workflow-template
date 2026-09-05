---
description: Fase de descubrimiento. Entender el problema y clasificar el tipo de proyecto.
---

Estás en **fase de descubrimiento**. Tu rol: analista + arquitecto senior que escucha antes de proponer.

**Restricciones de esta fase:**
- ❌ No escribes código
- ❌ No propones stack todavía
- ❌ No diseñas arquitectura
- ✅ Preguntas, escuchas, clasificas, documentas

---

## Paso 0 — Preguntar sobre graphify

Antes de cualquier análisis, pregunta al usuario:

> ¿Quieres instalar graphify para construir un grafo del proyecto? El grafo permite que Claude navegue el código sin hacer búsquedas masivas, reduce el consumo de tokens en sesiones futuras, detecta automáticamente "god nodes" (componentes críticos), y me ayuda a clasificar el tipo de proyecto automáticamente.
>
> - **Sí** → te guío para instalarlo ahora antes de continuar
> - **No** → continuamos sin grafo, yo detecto stack por archivos sueltos
> - **Ya está instalado** → verifico que `graphify-out/GRAPH_REPORT.md` existe y lo leo

**Si elige Sí y graphify no está instalado:**

```
Para instalarlo:
1. uv tool install graphifyy    (o: pipx install graphifyy)
2. graphify install              (registra el skill en tu editor)
3. Crea .graphifyignore antes de correr el análisis:

cat > .graphifyignore <<'EOF'
.aider.*
node_modules/
.venv/
venv/
__pycache__/
dist/
build/
.next/
*.log
graphify-out/
EOF

4. /graphify .   (el grafo lo construye el SKILL desde el asistente, no el CLI.
                  `graphify .` desde bash NO existe: el CLI solo tiene install,
                  update, query, extract, hook... Toma 1-5 min la primera vez.)
5. Cuando termine, avísame y continúo con el descubrimiento leyendo el grafo.
```

**Si elige No:** continúas sin grafo. No lo menciones más.

**Si ya está instalado:** lee `graphify-out/GRAPH_REPORT.md` completo antes de hacer cualquier pregunta.

---

## Paso 1 — Clasificar el tipo de proyecto

Esto es lo primero y más importante después del paso 0. Todo lo demás se construye sobre esta clasificación.

### Si existe el grafo de graphify

Léelo y clasifica automáticamente. El grafo te dice qué hay sin preguntar al usuario. Busca en `GRAPH_REPORT.md`:

- Sección "Backend Python Dependencies" o similar → indica backend en Python
- Nodos como "Next.js", "React", "Vue", "Angular" → indica frontend
- Nodos de "CLI", "click", "argparse", "typer" → indica herramienta CLI
- Estructura de paquete tipo `setup.py`, `pyproject.toml` con `[tool.poetry]` y sin servidor → librería
- Carpetas `ios/`, `android/`, archivos `pubspec.yaml`, `package.json` con React Native → móvil
- Carpetas separadas tipo `backend/` + `frontend/` → fullstack-monorepo

### Si NO existe el grafo

Pregunta al usuario directamente:

> ¿Qué tipo de proyecto es este? Algunas opciones:
> - **fullstack-monorepo** — backend + frontend en el mismo repo
> - **backend-only** — API/servicio sin frontend propio
> - **frontend-only** — SPA/app web sin backend propio
> - **cli** — herramienta de línea de comandos
> - **library** — librería para consumo de otros proyectos
> - **mobile** — app móvil (iOS/Android)
> - **etl-pipeline** — pipeline de datos
> - **microservices** — varios servicios independientes
> - **otro** — describir cuál

### Después de clasificar

Actualiza `CLAUDE.md` directamente — la sección "Tipo de proyecto" — con:
1. La **composición** (uno de los tipos de arriba)
2. Los **componentes principales** (qué carpetas hay y qué stack/framework tienen en cada una)

Ejemplo para un fullstack-monorepo (como musicos):
```
## Tipo de proyecto

**Composición:** fullstack-monorepo

**Componentes principales:**
- backend/ — FastAPI + SQLAlchemy + SQLite
- frontend/ — Next.js + TypeScript + Tailwind
```

Ejemplo para una CLI:
```
## Tipo de proyecto

**Composición:** cli

**Componentes principales:**
- src/ — código principal del comando
- tests/ — pruebas unitarias
```

**Confirma con el usuario** la clasificación antes de avanzar. Si dice que está mal, ajusta.

---

## Paso 2 — Detectar si es proyecto nuevo o existente

**Proyecto nuevo (no hay código):** ve directo al Paso 3.

**Proyecto existente (hay archivos, código):** produce `docs/discovery/01-existing-state.md` con:

```markdown
# Estado actual del proyecto — [fecha]

## Tipo de proyecto
[copia de CLAUDE.md]

## Stack detectado
[lenguajes, frameworks, librerías principales]

## Estructura principal (módulos/dominios)
[lo que el grafo o la inspección de carpetas reveló]

## God nodes (componentes más conectados)
[del grafo, si existe]

## Deuda técnica visible
[lo que se note en la primera inspección]

## Áreas opacas
[partes del código que no se entienden qué hacen]

## Preguntas para el usuario
[lo que necesita aclararse para entender el proyecto]
```

---

## Paso 3 — Entender el problema

Haz estas preguntas al usuario. Una a la vez, adaptando según respuestas:

1. ¿Qué problema resuelve este proyecto en una oración?
2. ¿Quién lo va a usar? (perfil concreto, no demografía)
3. ¿Cómo sé que funcionó? (1-3 métricas o resultados concretos)
4. ¿Qué NO es este proyecto? (cosas que parece pero no es)
5. ¿Qué restricciones hay? (tiempo, presupuesto, compliance, integraciones obligatorias)

Si algo es ambiguo, pregunta de nuevo. No asumas.

---

## Paso 3.5 — Fijar el norte del proyecto

La respuesta a la pregunta 1 del Paso 3 ("¿qué problema resuelve en una oración?") es la base del
**norte del proyecto**. Una vez que el usuario la responda y la confirmes:

1. Redacta el norte en 1-2 frases concretas — el propósito por el que existe el sistema, no la lista
   de features.
2. Actualiza la sección **"Norte del proyecto"** de `CLAUDE.md`, reemplazando el `[pendiente]`.
3. **Confirma el texto exacto con el usuario antes de escribirlo.** El norte es la referencia contra
   la que se contrastará cada cambio futuro (ver regla dura 9 y "Anclaje al norte" en CLAUDE.md), así
   que tiene que reflejar fielmente lo que el usuario quiere construir, no tu interpretación.

Ejemplo de un norte bien redactado:
```
**Este sistema existe para:** que un coordinador de eventos asigne músicos a fechas sin choques de
disponibilidad, reemplazando la hoja de cálculo manual que hoy genera dobles reservas.
```

Un norte mal redactado (demasiado vago o solo lista features):
```
**Este sistema existe para:** gestionar músicos, eventos, asignaciones, disponibilidad y reportes.
```
El primero dice *para qué*; el segundo solo dice *qué hace*. El norte debe permitir juzgar si un
cambio futuro sirve al propósito — una lista de features no permite eso.

---

## Paso 4 — Documentar

Escribe `docs/discovery/01-problem.md` (proyecto nuevo) o agrega al `01-existing-state.md` (proyecto existente):

```markdown
# Descubrimiento: [nombre del proyecto] — [fecha]

## Problema
## Usuario
## Métricas de éxito
## Fuera de alcance (no-goals)
## Restricciones
## Riesgos identificados
## Preguntas abiertas (sin respuesta todavía)
```

---

## Al terminar

Di exactamente esto:

> Descubrimiento listo.
> - Norte del proyecto fijado en CLAUDE.md: [el norte en una línea]
> - Tipo de proyecto clasificado en CLAUDE.md: [composición + componentes]
> - Output en `docs/discovery/`
> - Preguntas abiertas que necesitan respuesta: [lista o "ninguna"]
>
> Cuando quieras, ejecuta `/architect` para proponer stack y arquitectura.

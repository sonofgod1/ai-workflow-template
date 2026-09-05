---
description: Inicializa Git, estructura de branches y hooks de calidad. Ejecutar una sola vez al inicio del proyecto.
argument-hint: (sin argumentos)
---

Estás en **fase de inicialización Git**. Tu rol: configurar la infraestructura de control de versiones antes de que comience cualquier trabajo.

**Restricciones:**
- ✅ Configura estructura de branches
- ✅ Instala hooks de Git en .git/hooks/
- ✅ Prepara el commit inicial dejando los archivos en staging
- ✅ Configura CI, CODEOWNERS y branch protection
- ✅ Explica la estrategia al usuario
- ❌ **No hace commits, pushes ni tags.** Regla dura 3: el historial es del usuario.
  Preparas todo y le entregas los comandos listos para copiar.
- ❌ No toca código de aplicación
- ❌ No modifica CLAUDE.md ni archivos de docs
- ❌ No instala dependencias del proyecto

---

## Paso 0 — Leer contexto

Leer `CLAUDE.md` para entender si ya existe configuración de Git.

---

## Tu flujo

### Paso 1 — Verificar estado del repositorio

```bash
git rev-parse --git-dir  > /dev/null 2>&1 && echo "REPO_EXISTS" || echo "NO_REPO"
git rev-parse HEAD       > /dev/null 2>&1 && echo "TIENE_COMMITS" || echo "SIN_COMMITS"
```

**Si no existe repo:** `git init` (crear el repo no es tocar el historial).

**Si no hay commits todavía:** deja los archivos del workflow en staging. Uno por uno y
solo los que existan — nunca `git add .`, y no todos los proyectos instalan lo mismo:

```bash
for p in CLAUDE.md .claude .github git-hooks docs .gitignore .graphifyignore \
         sync-workflow.sh generate-cursor-rules.sh graphify-out/.gitkeep; do
  [ -e "$p" ] && git add "$p"
done
git status --short
```

Revisa el `git status` antes de seguir: si aparece algo que no debería versionarse
(`.env`, `*.db`, `node_modules/`), quítalo del staging y añádelo a `.gitignore`.

**No commitees.** El commit va en el bloque del paso 5, para que lo ejecute el usuario.

**Si ya hay commits:** no hay nada que preparar. Continúa al paso 2.

---

### Paso 2 — Crear estructura de branches

Crear branches no toca el historial, así que esto sí lo haces tú **siempre que ya
exista al menos un commit**. Si el repo está vacío, no se puede: salta al paso 3 y
deja los comandos de branches en el bloque del paso 5.

```bash
# Asegurarse de estar en main (o master)
git checkout main 2>/dev/null || git checkout master 2>/dev/null || true

# Crear branch develop
git checkout -b develop 2>/dev/null || git checkout develop
git checkout main 2>/dev/null || git checkout master 2>/dev/null || true
```

Explicar la estrategia al usuario:

```
ESTRATEGIA DE BRANCHES
─────────────────────────────────────────────────────────────
main            Solo código listo para producción.
                Nunca se trabaja aquí directamente.
                Recibe merges desde develop (releases) o hotfix/* (emergencias).
                Cada merge genera un tag semver (v1.0.0, v1.1.0, etc.)

develop         Branch de integración continua.
                Aquí se mergean las features terminadas.
                Siempre debe estar en estado funcional (tests pasan).

feature/[slug]  Una branch por feature o cambio significativo.
                Se crea desde develop, se mergea a develop con --no-ff.
                → git checkout develop && git checkout -b feature/mi-feature

fix/[slug]      Corrección de bug no urgente.
                Se crea desde develop, se mergea a develop.

hotfix/[slug]   Arreglo urgente en producción.
                Se crea desde main, se mergea a main Y a develop.
                → git checkout main && git checkout -b hotfix/mi-arreglo
─────────────────────────────────────────────────────────────
```

---

### Paso 3 — Instalar hooks de Git

Los hooks están en `git-hooks/` (versionados en el repo). Copiarlos a `.git/hooks/`:

```bash
cp git-hooks/pre-commit  .git/hooks/pre-commit
cp git-hooks/pre-push    .git/hooks/pre-push
cp git-hooks/commit-msg  .git/hooks/commit-msg
chmod +x .git/hooks/pre-commit .git/hooks/pre-push .git/hooks/commit-msg
```

Explicar qué hace cada hook:

```
HOOKS DE GIT INSTALADOS
─────────────────────────────────────────────────────────────
pre-commit    Antes de cada commit:
              • Bloquea archivos prohibidos (.env, *.db, node_modules, etc.)
              • Lint de JS/TS (biome o eslint si está instalado)
              • Type-check TypeScript si hay tsconfig.json
              • Lint Python con ruff si hay pyproject.toml

pre-push      Antes de cada push:
              • Corre tests (npm test / pytest según stack detectado)
              • Advierte si el push es directo a main

commit-msg    Valida formato de commits convencionales:
              • tipo(scope): descripción
              • Rechaza commits que no sigan el formato
─────────────────────────────────────────────────────────────
```

---

### Paso 4 — Configurar Git local

```bash
git config --local core.hooksPath .git/hooks
```

Si hay remote configurado:
```bash
git remote -v
```

Si no hay remote todavía, recordar al usuario que deberá agregarlo:
```bash
# Cuando tengas el repo en GitHub/GitLab:
git remote add origin https://github.com/usuario/proyecto.git
git push -u origin main
git push -u origin develop
```

---

### Paso 5 — Entregar los comandos de historial

Aquí no ejecutas nada. Reúnes en **un solo bloque copiable** todo lo que toca el
historial, en orden, y se lo das al usuario.

Si el repo no tenía commits (todo quedó en staging en el paso 1):

```bash
git commit -m "chore: workflow inicializado"
git checkout -b develop
git checkout main
git tag -a v0.0.1 -m "chore: workflow inicializado"
```

Si el repo ya tenía commits y ya creaste las branches en el paso 2, solo falta el tag:

```bash
git tag -a v0.0.1 -m "chore: workflow inicializado"
```

Di explícitamente: *"Estos comandos los ejecutas tú — regla dura 3. Cuando termines,
avísame y verifico que quedó todo bien."* Y cuando el usuario confirme, verifica con
`git log --oneline`, `git branch` y `git tag`.

---

### Paso 6 — Protección del lado del servidor

Los hooks de Git corren en la máquina del desarrollador y `--no-verify` los anula. Esta es la capa
que no se puede saltar, y es la única que protege igual sin importar con qué editor se trabaje.

**a) Completar CODEOWNERS.**

`.github/CODEOWNERS` viene con `@TU-USUARIO` como marcador. GitHub ignora el archivo entero si no se
reemplaza. Preguntar al usuario su usuario u organización de GitHub y sustituirlo:

```bash
gh api user --jq .login          # tu usuario, si no lo recuerdas
sed -i '' 's/@TU-USUARIO/@tu-usuario-real/g' .github/CODEOWNERS   # macOS
sed -i    's/@TU-USUARIO/@tu-usuario-real/g' .github/CODEOWNERS   # Linux
```

**b) Activar branch protection en `main` y `develop`.**

Requiere que el repo ya exista en GitHub y que `gh` esté autenticado. Mostrar estos comandos al
usuario para que los ejecute — no los ejecutes tú sin confirmación, porque cambian la configuración
del repositorio remoto:

```bash
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)

for BRANCH in main develop; do
  gh api -X PUT "repos/$REPO/branches/$BRANCH/protection" \
    -H "Accept: application/vnd.github+json" \
    -f "required_status_checks[strict]=true" \
    -f "required_status_checks[contexts][]=archivos-prohibidos" \
    -f "required_status_checks[contexts][]=secretos" \
    -f "required_pull_request_reviews[require_code_owner_reviews]=true" \
    -f "required_pull_request_reviews[required_approving_review_count]=1" \
    -f "enforce_admins=false" \
    -f "restrictions=null"
done
```

Si el repo es privado y la cuenta es Free, la API de branch protection no está disponible. En ese
caso indicar la ruta manual: **Settings → Branches → Add rule**, y marcar "Require a pull request
before merging", "Require review from Code Owners" y "Require status checks to pass".

**c) Explicar qué quedó protegido:**

```
PROTECCIÓN DEL SERVIDOR
─────────────────────────────────────────────────────────────
CI (.github/workflows/ci.yml)   Corre en cada PR a main y develop:
                                • archivos prohibidos versionados
                                • formato convencional de TODOS los commits
                                • secretos (gitleaks)
                                • lint, type-check y tests según el stack

CODEOWNERS                      Cambios a docs/adr/, docs/contracts/, la
                                gobernanza y el propio CI exigen tu aprobación.

Branch protection               main y develop solo reciben cambios por PR,
                                con CI en verde y review aprobada.
─────────────────────────────────────────────────────────────

Por qué importa: los hooks locales se saltan con --no-verify y solo existen en
la máquina donde se instalaron. Esto corre en el servidor y aplica a cualquier
editor y a cualquier persona del equipo.
```

---

### Paso 7 — Mostrar resumen final

Marca con `✓` solo lo que de verdad hiciste. Lo que dejaste en manos del usuario va
con `⧗` y se repite abajo. No declares hecho lo que todavía depende de que él ejecute
el bloque del paso 5.

```
RESUMEN — Git configurado
─────────────────────────────────────────────────────────────
BRANCHES
  [✓ si ya existían commits y las creaste / ⧗ si van en el bloque del paso 5]
  main      (producción — siempre deployable)
  develop   (integración continua)

HOOKS DE GIT
  ✓ pre-commit    (lint + archivos prohibidos)
  ✓ pre-push      (tests)
  ✓ commit-msg    (formato convencional)

HOOKS DE CLAUDE CODE
  ✓ check-protected.sh   (protege archivos críticos)
  ✓ check-branch.sh      (advierte trabajo en main)
  ✓ check-bash.sh        (bloquea comandos destructivos)
  ✓ lint-on-save.sh      (lint automático al guardar)
  ✓ session-summary.sh   (resumen al terminar sesión)

PROTECCIÓN DEL SERVIDOR
  ✓ CI en cada PR      (archivos, commits, secretos, lint, tests)
  [✓/⧗] CODEOWNERS     (⧗ si sigue con @TU-USUARIO sin reemplazar)
  [✓/⧗] Branch protection  (⧗ si no hay remote todavía)

TAG
  ⧗ v0.0.1             (lo pones tú, ver bloque de abajo)

PENDIENTE — LO EJECUTAS TÚ (regla dura 3)
  [pega aquí el bloque del paso 5]

REFERENCIA RÁPIDA DE GIT
  Nueva feature:     git checkout develop && git checkout -b feature/[slug]
  Commit:            git add <archivos> && git commit -m "tipo(scope): desc"
  Mergear feature:   git checkout develop && git merge feature/[slug] --no-ff
  Release a main:    git checkout main && git merge develop --no-ff -m "release: desc"
  Tag de release:    git tag -a v1.0.0 -m "release: descripción"
  Push con tags:     git push origin main --follow-tags
  Sincronizar dev:   git checkout develop && git merge main && git push origin develop
─────────────────────────────────────────────────────────────
```

---

## Al terminar

```
Git preparado. Hooks instalados: pre-commit, pre-push, commit-msg.
Los comandos de arriba los ejecutas tú — yo no toco el historial.
Cuando termines, avísame y verifico. Después, /discovery para empezar el proyecto.
```

#!/usr/bin/env bash
# .claude/hooks/lib-root.sh
# Resuelve la raíz del proyecto para hooks y scripts. Se sourcea, no se ejecuta.
#
# El problema que resuelve: CLAUDE_PROJECT_DIR apunta al checkout desde el que se
# lanzó la sesión, no al worktree en el que se está trabajando. Con dos agentes en
# dos worktrees del mismo repositorio, los dos escribían el estado de fase del
# checkout principal: un candado global disfrazado de estado local, y el segundo
# agente pisaba la fase del primero sin que nada avisara.
#
# Preferir siempre el worktree tampoco sirve: si la sesión trabaja fuera del
# proyecto (--add-dir a otro repositorio), `git rev-parse` resolvería OTRO
# repositorio y los hooks de protección leerían el protected.txt equivocado. Un
# hook de protección apuntando al repo de al lado es peor que no tenerlo.
#
# Así que se usa el worktree SOLO si es del mismo repositorio que
# CLAUDE_PROJECT_DIR, comparando el git-common-dir de los dos. Si no coinciden, o
# si no hay git, manda CLAUDE_PROJECT_DIR.

# Raíz del repositorio o worktree que contiene un directorio dado.
_wf_toplevel() {
  git -C "$1" rev-parse --show-toplevel 2>/dev/null
}

# El .git compartido por todos los worktrees de un repositorio: su identidad.
_wf_common_dir() {
  local d
  d=$(git -C "$1" rev-parse --git-common-dir 2>/dev/null) || return 1
  case "$d" in
    /*) ;;
    *) d="$1/$d" ;;
  esac
  (cd "$d" 2>/dev/null && pwd -P) || return 1
}

# Resuelve symlinks: si el proyecto se alcanza por dos rutas (p.ej. ~/projects
# como symlink a /Volumes/Datos/projects) y una llega por cada una, el prefijo no
# se recorta, ningún patrón coincide, y el hook deja pasar la escritura callado.
_wf_realpath() {
  (cd "$1" 2>/dev/null && pwd -P) || echo "$1"
}

# Raíz del checkout PRINCIPAL del repositorio, no del worktree actual.
#
# Hace falta para la configuración que no se versiona: un worktree no la tiene, y
# sin este fallback cualquier flujo que corra dentro de un worktree se comporta
# como si el proyecto no hubiera configurado nada. El git-common-dir es el .git
# compartido; su directorio padre es el checkout principal.
wf_main_root() {
  local c
  c=$(_wf_common_dir "$(_wf_toplevel "." || echo .)" 2>/dev/null) || { wf_root; return; }
  case "$c" in
    */.git) _wf_realpath "${c%/.git}" ;;
    *) wf_root ;;
  esac
}

# Uso: ROOT=$(wf_root)
wf_root() {
  local base aqui
  base="${CLAUDE_PROJECT_DIR:-}"

  aqui=$(_wf_toplevel ".")
  if [ -z "$base" ]; then
    _wf_realpath "${aqui:-$PWD}"
    return
  fi

  if [ -n "$aqui" ]; then
    local c_base c_aqui
    c_base=$(_wf_common_dir "$base" 2>/dev/null)
    c_aqui=$(_wf_common_dir "." 2>/dev/null)
    if [ -n "$c_base" ] && [ "$c_base" = "$c_aqui" ]; then
      # Mismo repositorio: el worktree actual es la raíz correcta.
      _wf_realpath "$aqui"
      return
    fi
  fi

  _wf_realpath "$base"
}

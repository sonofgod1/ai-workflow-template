#!/usr/bin/env bash
# .claude/hooks/check-writes.sh
# PreToolUse — envoltura fina sobre .workflow/write-guard.py.
#
# Cubre dos cosas que antes no cubría nadie:
#   1. Escrituras a archivos protegidos vía Bash (`cat >`, `tee`, `sed -i`, `cp`...).
#      check-protected.sh solo ve Write/Edit; check-bash.sh solo veía borrados.
#   2. La política de escritura de la fase activa (.workflow/.phase.json).
#
# Falla abierto a propósito: si falta python3 o el guardia se rompe, no puede
# dejar el proyecto sin poder escribir nada.

set -uo pipefail

# lib-root.sh resuelve el worktree actual cuando es del mismo repositorio que
# CLAUDE_PROJECT_DIR, y CLAUDE_PROJECT_DIR en cualquier otro caso. Sin eso, dos
# agentes en dos worktrees leen y escriben el estado del checkout principal.
LIB="$(dirname "${BASH_SOURCE[0]}")/lib-root.sh"
if [ -f "$LIB" ]; then
  # shellcheck source=/dev/null
  . "$LIB"
  ROOT="$(wf_root)"
else
  ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
fi
GUARD="$ROOT/.workflow/write-guard.py"

[ -f "$GUARD" ] || exit 0
command -v python3 > /dev/null 2>&1 || exit 0

CLAUDE_PROJECT_DIR="$ROOT" python3 "$GUARD" check
exit $?

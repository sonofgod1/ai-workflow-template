#!/usr/bin/env bash
# .claude/hooks/check-branch.sh
# PreToolUse — advierte si se está trabajando directamente en main
# No bloquea — el usuario puede estar haciendo un hotfix deliberado

if ! git rev-parse --git-dir > /dev/null 2>&1; then
  exit 0
fi

CURRENT_BRANCH=$(git branch --show-current 2>/dev/null)

if [ -z "$CURRENT_BRANCH" ]; then
  exit 0
fi

if [ "$CURRENT_BRANCH" = "main" ] || [ "$CURRENT_BRANCH" = "master" ]; then
  echo ""
  echo "⚠️  ADVERTENCIA: Estás trabajando directamente en '$CURRENT_BRANCH'"
  echo ""
  echo "main debe mantenerse siempre deployable. El trabajo directo aquí"
  echo "dificulta la revisión y rompe el flujo de integración continua."
  echo ""
  echo "Si esto es un hotfix deliberado, puedes continuar."
  echo "Si no, crea una branch antes de continuar:"
  echo ""
  echo "  git checkout develop"
  echo "  git checkout -b feature/[descripción-corta]"
  echo ""
  echo "  O para un hotfix urgente:"
  echo "  git checkout -b hotfix/[descripción-corta]"
  echo ""
  # Exit 0 = advertencia, no bloqueo
  exit 0
fi

exit 0

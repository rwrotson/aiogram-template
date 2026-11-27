#!/usr/bin/env bash
# PostToolUse: format and autofix an edited Python file; report remaining errors to Claude.
set -uo pipefail

project="${CLAUDE_PROJECT_DIR:-$(pwd)}"
file="$(jq -r '.tool_input.file_path // empty')"

case "$file" in
  *.py | *.pyi) ;;
  *) exit 0 ;;
esac
case "$file" in
  "$project"/*) ;;
  *) exit 0 ;;
esac
[ -f "$file" ] || exit 0

source "${BASH_SOURCE[0]%/*}/failure-summary.sh"
cd "$project" || exit 0
if out=$(uv run --quiet ruff format --quiet "$file" 2>&1); then
  :
else
  hook_failure 'ruff format' "$?" <<< "$out"
  exit 2
fi
if out=$(uv run --quiet ruff check --fix --quiet --output-format concise "$file" 2>&1); then
  exit 0
else
  hook_failure 'ruff check' "$?" <<< "$out"
  exit 2
fi

#!/usr/bin/env bash
# Compare dirty Python state before the prompt and at Stop.
set -uo pipefail

source "${BASH_SOURCE[0]%/*}/failure-summary.sh"

python_state() {
  GIT_OPTIONAL_LOCKS=0 git status --porcelain=v2 -z --no-renames --untracked-files=all -- '*.py' '*.pyi' |
    (
      if ! IFS= read -r -d '' record; then
        printf 'clean\n'
        exit 0
      fi

      {
        while :; do
          # Porcelain v2 records include the index IDs. Strip fixed fields without splitting the path.
          case "$record" in
            '1 '*) fields=8 ;;
            'u '*) fields=10 ;;
            '? '*) fields=1 ;;
            *) exit 1 ;;
          esac
          path="$record"
          for ((i = 0; i < fields; i++)); do path="${path#* }"; done

          if [[ -L "$path" ]]; then
            hash=$(readlink "./$path" | git hash-object --stdin) || exit 1
            kind=link
          elif [[ -f "$path" ]]; then
            hash=$(git hash-object --no-filters -- "$path") || exit 1
            kind=file
          else
            hash=-
            kind=missing
          fi
          printf '%s\0%s\0%s\0' "$record" "$kind" "$hash"
          IFS= read -r -d '' record || break
        done
      } | git hash-object --stdin
    )
}

payload=$(jq -r '[.stop_hook_active // false, .session_id // ""] | @tsv') || exit 0
IFS=$'\t' read -r active session <<< "$payload"
[[ "$active" == true ]] && exit 0

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" || exit 0
root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$root" || exit 0

baseline=
if [[ "$session" =~ ^[A-Za-z0-9_-]{1,128}$ ]] && git_dir=$(git rev-parse --absolute-git-dir 2>/dev/null); then
  baseline="$git_dir/claude-python-$session"
fi

if [[ "${1:-}" == snapshot ]]; then
  [[ -n "$baseline" ]] || exit 0
  if state=$(python_state 2>/dev/null) && tmp=$(mktemp "$baseline.XXXXXX" 2>/dev/null); then
    if printf '%s\n' "$state" > "$tmp" && mv -f -- "$tmp" "$baseline"; then
      exit 0
    fi
    rm -f -- "$tmp"
  fi
  rm -f -- "$baseline"
  exit 0
fi

previous=
if [[ -f "$baseline" ]]; then
  IFS= read -r previous < "$baseline"
  rm -f -- "$baseline"
fi
if state=$(python_state 2>/dev/null) && [[ "$state" == clean || "$state" == "$previous" ]]; then
  exit 0
fi

if out=$(RUFF_OUTPUT_FORMAT=concise uv run --quiet poe quick 2>&1); then
  exit 0
else
  hook_failure 'poe quick' "$?" <<< "$out"
  exit 2
fi

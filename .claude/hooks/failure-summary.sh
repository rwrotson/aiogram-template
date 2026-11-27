# Print a bounded diagnostic summary from stdin.
hook_failure() {
  printf '%s failed (exit %s):\n' "$1" "$2"
  LC_ALL=C awk '
    function show(i) {
      if (length(lines[i]) > 320) {
        print substr(lines[i], 1, 317) "..."
        clipped = 1
      } else {
        print lines[i]
      }
      shown++
    }
    /^[[:space:]-]*$/ { next }
    {
      lines[++n] = $0
      if (tolower($0) ~ /^[[:space:]]*broken contracts[[:space:]]*$/) contracts = n
      if ($0 ~ /:[0-9]+(:[0-9]+)?:/ || tolower($0) ~ /^[[:space:]]*(error|fatal)(:|[[:space:]])/) {
        diagnostics[++count] = n
      }
    }
    END {
      if (contracts) {
        for (i = contracts; i <= n && shown < 8; i++) show(i)
      } else if (count) {
        for (i = 1; i <= count && shown < 8; i++) show(diagnostics[i])
      } else {
        for (i = 1; i <= n; i++) if (i <= 4 || i > n - 4) show(i)
      }
      if (shown < n || clipped) print "[Output truncated]"
    }
  '
} >&2

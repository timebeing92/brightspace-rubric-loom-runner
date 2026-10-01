#!/usr/bin/env bash
# Shared by managed and portable launchers; works with macOS Bash 3.2.
python_ok() {
  local py="$1"
  local probe_pid attempt
  "$py" -I -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)' </dev/null >/dev/null 2>&1 &
  probe_pid=$!
  # Do not rely on GNU timeout (absent on a standard macOS installation),
  # or on another Python interpreter being available to supervise this one.
  for ((attempt=0; attempt<50; attempt++)); do
    if ! kill -0 "$probe_pid" 2>/dev/null; then
      wait "$probe_pid" 2>/dev/null
      return $?
    fi
    sleep 0.1
  done
  # This is only our disposable startup probe, never the user's active Loom.
  kill -KILL "$probe_pid" 2>/dev/null || true
  wait "$probe_pid" 2>/dev/null || true
  return 1
}

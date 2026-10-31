#!/usr/bin/env bash
# Run a command; on failure emit its output tail as a check-run annotation.
#
# Why: job logs are served from a host that is not always reachable from where this is being
# watched, but check-run annotations come through the API. Without this, a red step is just a red
# step with no reason attached.
set -uo pipefail
name="$1"; shift
log="/tmp/ci_$(echo "$name" | tr ' /' '__').log"
if "$@" >"$log" 2>&1; then
  tail -n 6 "$log"
else
  rc=$?
  echo "::error::'$name' failed (exit $rc): $(tail -c 900 "$log" | tr '\n' '|' | tr -d '\r')"
  echo "---- full tail ----"
  tail -n 60 "$log"
  exit 1
fi

#!/bin/sh
# Runs every end-to-end test against a private herdr server. Needs herdr, fzf and pyte.
cd "$(dirname "$0")" || exit 1
status=0
for test in test_*.py; do
  echo "== $test"
  python3 "$test" || status=1
done
exit $status

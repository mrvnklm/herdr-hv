#!/bin/sh
# PostToolUse: report German text in the file Claude just wrote, while it is still open.
file=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("tool_input",{}).get("file_path",""))')
[ -z "$file" ] && exit 0
cd "$CLAUDE_PROJECT_DIR" || exit 0
rel=$(python3 -c 'import os,sys; print(os.path.relpath(sys.argv[1]))' "$file")
case "$rel" in ../*) exit 0 ;; esac
python3 scripts/check_english.py --files "$rel" >&2 || exit 2

#!/bin/sh
cd "$(dirname "$0")" || exit 1
if command -v python3.12 >/dev/null 2>&1; then
  exec python3.12 start_demo.py
fi
if command -v python3 >/dev/null 2>&1; then
  exec python3 start_demo.py
fi
echo 'Install Python 3.12 from python.org, then open Start Demo.command again.'
read -r _

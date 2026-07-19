#!/usr/bin/env bash
cd "$(dirname "$0")"
(sleep 1; xdg-open http://localhost:8765/ 2>/dev/null || open http://localhost:8765/ 2>/dev/null) &
python -m http.server 8765

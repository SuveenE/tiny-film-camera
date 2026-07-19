#!/usr/bin/env bash
set -euo pipefail

sudo systemctl restart \
  tiny-film-web.service \
  tiny-film-shutter.service \
  tiny-film-battery.service

echo "All systems have been restarted"

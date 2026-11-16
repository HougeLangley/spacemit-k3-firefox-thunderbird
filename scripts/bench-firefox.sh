#!/bin/bash
# Headless smoke/benchmark for a Firefox install tree.
set -euo pipefail
ff="${1:-/usr/bin/firefox}"
page="${2:-/mnt/k3work/firefox-k3/bench.html}"
echo "Firefox: $ff"
"$ff" --version
echo "--- headless screenshot timing ---"
/usr/bin/time -f 'wall=%e user=%U sys=%S maxrss=%MKB' \
  xvfb-run -a "$ff" --headless --no-remote --profile /tmp/k3-ff-profile \
  --screenshot /tmp/k3-firefox-shot.png "$page"
ls -lh /tmp/k3-firefox-shot.png

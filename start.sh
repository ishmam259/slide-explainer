#!/usr/bin/env bash
# Slide Explainer launcher (macOS / Linux).
#   ./start.sh         demo mode: no API key, no cost (built-in offline model)
#   ./start.sh --live  live mode: needs backend/.env with OPENAI_API_KEY
set -euo pipefail
root="$(cd "$(dirname "$0")" && pwd)"
live=0; [[ "${1:-}" == "--live" ]] && live=1

command -v uv >/dev/null || { echo "Install uv first: curl -LsSf https://astral.sh/uv/install.sh | sh"; exit 1; }
command -v npm >/dev/null || { echo "Install Node.js LTS first: https://nodejs.org"; exit 1; }
if (( live )) && [[ ! -f "$root/backend/.env" ]]; then
  echo "Live mode needs backend/.env: cp backend/.env.example backend/.env and set OPENAI_API_KEY"; exit 1
fi

echo "-> Installing backend dependencies"
uv --directory "$root/backend" sync --quiet
if [[ "$(uv --directory "$root/backend" run python -c 'from slidex.core.hardware import chromium_installed; print(chromium_installed())')" != "True" ]]; then
  echo "-> Installing Chromium for PDF export (one time)"
  uv --directory "$root/backend" run playwright install chromium
fi
[[ -d "$root/frontend/node_modules" ]] || npm --prefix "$root/frontend" install --no-audit --no-fund

if (( live )); then export SLIDEX_FAKE_LLM=0 SLIDEX_DATA_DIR=../data; mode="LIVE"
else export SLIDEX_FAKE_LLM=1 SLIDEX_DEMO_WEB=1 SLIDEX_DATA_DIR=../data-demo; mode="DEMO (offline, free)"; fi

uv --directory "$root/backend" run slidex serve & back=$!
npm --prefix "$root/frontend" run dev & front=$!
trap 'kill $back $front 2>/dev/null' EXIT INT TERM
echo "-> Waiting for http://localhost:3000"
for _ in $(seq 90); do curl -fs http://localhost:3000 >/dev/null && break; sleep 2; done
(command -v open >/dev/null && open http://localhost:3000) || (command -v xdg-open >/dev/null && xdg-open http://localhost:3000) || true
echo "Slide Explainer is running in $mode mode. Press Ctrl+C to stop."
wait

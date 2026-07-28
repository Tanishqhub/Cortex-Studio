#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "--- Building frontend ---"
cd frontend
npm ci
npm run build
cd ..

echo "--- Installing backend dependencies ---"
cd backend
source venv/bin/activate
pip install -r requirements.txt

echo "--- Running DB migrations ---"
set -a
source .env
set +a
flask db upgrade

echo "--- Restarting service ---"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
systemctl --user restart cortex-studio

echo "--- Deploy complete ---"

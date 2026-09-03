#!/usr/bin/env bash
set -euo pipefail

bash scripts/dev-doctor.sh

printf '\nInstalling frontend dependencies from package-lock.json...\n'
npm ci

printf '\nSyncing the locked lightweight backend + dev environment...\n'
uv sync --project backend --locked --no-group worker

printf '\nBootstrap complete.\n'
printf 'Run npm run check:fast for the ordinary local gate.\n'
printf 'Worker/model development additionally needs: uv sync --project backend --locked --group worker\n'
printf 'Browser E2E additionally needs Playwright Chromium: npx playwright install chromium\n'
printf 'Database verification additionally needs Docker + Supabase CLI 2.113.0 + tbls 1.95.0 + ffmpeg.\n'
printf 'Real-stack verification additionally needs Docker + the Supabase CLI.\n'

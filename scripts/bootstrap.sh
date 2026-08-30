#!/usr/bin/env bash
set -euo pipefail

bash scripts/dev-doctor.sh

printf '\nInstalling frontend dependencies from package-lock.json...\n'
npm ci

printf '\nSyncing the locked backend environment...\n'
uv sync --project backend --locked

printf '\nBootstrap complete.\n'
printf 'Run npm run check:fast for the ordinary local gate.\n'
printf 'Browser E2E additionally needs Playwright Chromium: npx playwright install chromium\n'
printf 'Database/real-stack tiers additionally need Docker + the Supabase CLI.\n'

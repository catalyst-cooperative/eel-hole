# AGENTS

- Use `uv` to run Python project commands.
- Run tests with `uv run pytest ...` (not bare `pytest`).
- Run `npm run build` after TypeScript/JavaScript/CSS changes.
- Use Prettier to format TypeScript and HTML files.

## Integration test workflow

- Build frontend assets before starting the app: `npm run build`.
- Start services with integration-test auth bypass: `PUDL_VIEWER_INTEGRATION_TEST=true docker compose up -d`.
- Use `--build` only when image layers/dependencies changed.
- This project uses bind mounts, so most code/template changes do not require rebuilds or container restarts.
- After Python changes, Flask `--reload` may restart and re-index remote datapackages; wait for startup to settle (~25s) before running integration tests.
- Use `logs -f` to follow startup/reload output and confirm readiness before Playwright runs.
- Apply DB migrations: `docker compose exec eel_hole uv run flask db upgrade`.
- Run integration tests: `uv run pytest tests/integration`.
- Install Playwright Chromium only when missing (not every run): `uv run playwright install chromium`.

## Debugging tool

- For backend failures during integration tests, inspect recent app logs:
  `docker compose logs -f eel_hole --tail 300`

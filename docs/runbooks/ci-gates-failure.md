## CI gates failure runbook

### Quick triage checklist
1. **Ruff**: `ruff check .` and `ruff format --check .`
2. **Tests**: `pytest -q`
3. **Security**:
   - `bandit -r src -ll`
   - `pip-audit --progress-spinner off`
4. **Env contract**:
   - `python scripts/validate_env_contract.py --env-file .env.example`
5. **Migrations**:
   - `python scripts/wait_for_db.py --timeout-seconds 30`
   - `alembic upgrade head`

### Notes
- If `Security Gates` fails on env parsing, check JSON-only fields like `CORS_ALLOW_ORIGINS`.


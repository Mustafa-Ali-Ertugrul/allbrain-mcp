.PHONY: install lint security test stress stress-mcp bump-patch ci-local

install:
	uv sync --group dev

lint:
	uv run ruff check --exit-zero src/ tests/
	uv run ruff format --check src/ tests/ || true
	uv run python scripts/check_complexity.py
	uv run python scripts/check_architecture.py

security:
	uv run bandit -c pyproject.toml -r src/ -ll

test:
	uv run pytest --cov --cov-report=term-missing --cov-fail-under=80 -n auto --dist=worksteal

stress:
	uv run python scripts/stress_test.py

stress-mcp:
	uv run python scripts/mcp_stress_test.py

bump-patch:
	uv run bump-my-version bump patch --dry-run --verbose --allow-dirty

ci-local: install lint security test
	@echo "=== CI pipeline passed locally ==="

.PHONY: install lint security test stress stress-mcp ci-local

install:
	uv sync --only-dev

lint:
	uv run ruff check --exit-zero src/ tests/
	uv run ruff format --check --exit-zero src/ tests/

security:
	uv run bandit -c pyproject.toml -r src/ -ll

test:
	uv run pytest --cov --cov-report=term-missing --cov-fail-under=60 -n auto --dist=worksteal

stress:
	uv run python scripts/stress_test.py

stress-mcp:
	uv run python scripts/mcp_stress_test.py

ci-local: install lint security test
	@echo "=== CI pipeline passed locally ==="

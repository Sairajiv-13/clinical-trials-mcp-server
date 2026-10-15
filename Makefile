PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip

.PHONY: setup test lint run run-http docker

setup:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

test:
	$(PYTHON) -m pytest --cov=clinical_trials_mcp --cov-report=term

lint:
	.venv/bin/ruff check src tests examples
	.venv/bin/ruff format --check src tests examples

run:
	$(PYTHON) -m clinical_trials_mcp.server

run-http:
	$(PYTHON) -m clinical_trials_mcp.server --transport http --host 127.0.0.1 --port 8000

docker:
	docker build -t clinical-trials-mcp-server .
	docker run --rm -p 8000:8000 clinical-trials-mcp-server

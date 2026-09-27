# Baby Monitor — developer tasks
#
# `make verify` is the single verification gate (see AGENTS.md). It runs, in order:
#   1. lint        (ruff check)
#   2. format-check (ruff format --check)
#   3. typecheck   (mypy)
#   4. test        (pytest)

PYTHON ?= python3
VENV   ?= .venv
BIN     = $(VENV)/bin

.PHONY: help venv install verify lint format format-check typecheck test clean

help:
	@echo "Targets:"
	@echo "  make venv          Create the local virtualenv ($(VENV))"
	@echo "  make install       Install runtime + dev dependencies into the venv"
	@echo "  make verify        Run the full gate: lint, format-check, typecheck, test"
	@echo "  make lint          Run ruff lint checks"
	@echo "  make format        Auto-format the code with ruff"
	@echo "  make format-check  Check formatting without changing files"
	@echo "  make typecheck     Run mypy on app/"
	@echo "  make test          Run pytest"
	@echo "  make clean         Remove caches and the virtualenv"

venv:
	$(PYTHON) -m venv $(VENV)

install: venv
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt -r requirements-dev.txt

verify: lint format-check typecheck test

lint:
	$(BIN)/ruff check .

format:
	$(BIN)/ruff format .

format-check:
	$(BIN)/ruff format --check .

typecheck:
	$(BIN)/mypy app

test:
	$(BIN)/pytest

clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

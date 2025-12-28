.PHONY: bootstrap test eval-smoke eval

PYTHON ?= python3
VENV ?= .venv
VENV_PY := $(VENV)/bin/python
PIP := $(VENV_PY) -m pip

bootstrap:
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -U pip
	$(PIP) install -e ".[dev,agents,synth]"

test:
	$(VENV_PY) -m pytest -q

eval-smoke:
	$(VENV_PY) -m praxis_evals.run_local --case praxis_evals/cases/smoke.yaml

eval: test eval-smoke

.PHONY: test eval-smoke eval

test:
	python -m pytest -q

eval-smoke:
	python -m praxis_evals.run_local --case praxis_evals/cases/smoke.yaml

eval: test eval-smoke

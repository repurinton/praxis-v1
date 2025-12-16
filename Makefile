.PHONY: test eval-smoke eval

test:
	pytest -q

eval-smoke:
	python -m evals.run_local --case evals/cases/smoke.yaml

eval: test eval-smoke

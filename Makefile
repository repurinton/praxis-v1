.PHONY: test eval-smoke eval

test:
\tpytest -q

eval-smoke:
\tpython -m evals.run_local --case evals/cases/smoke.yaml

eval: test eval-smoke

PY=python
.PHONY: all dataset test baselines aggregate
all:
	$(PY) -m src.backend1
dataset:
	$(PY) -m src.features.build_dataset
test:
	$(PY) run_tests.py
baselines:
	$(PY) -m src.evaluation.run_baselines
aggregate:
	$(PY) -m src.evaluation.aggregate

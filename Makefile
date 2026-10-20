PY=python
.PHONY: all synth dataset test baselines aggregate report clean
all: synth dataset test baselines aggregate report
synth:      ; $(PY) -m src.data.synthetic          # bỏ qua khi đã có dữ liệu thật trong data/raw
dataset:    ; $(PY) -m src.features.build_dataset
test:       ; $(PY) run_tests.py
baselines:  ; $(PY) -m src.evaluation.run_baselines
aggregate:  ; $(PY) -m src.evaluation.aggregate
report:     ; $(PY) -m src.evaluation.make_report
clean:      ; rm -f outputs/forecasts/* outputs/tables/* outputs/figures/* paper/chapter5_results.md

# Backend 4 risk outputs (corrected)

`{coin}_{model}.parquet`: all scheduled 2021–2025 h=1 dates, two windows,
alpha .05/.01 (95%/99%). Returns/VaR/ES/sigma in percent; variance in %².
`status` and `score_valid` distinguish missing predictions from zero breaches.
`common_sample` identifies common valid dates across all 9 models per coin/window/alpha.

- backtest.csv: primary common-sample VaR backtests and quantile loss.
- backtest_available_sample.csv: each model's own available sample; not a fair ranking.
- coverage.csv: counts, first/last valid dates, unavailable reasons.
- crisis_breaches.csv: common and available samples; COVID 2020 explicitly outside evaluation.
- simulation_checks.csv: six deterministic checks with known simulated tail rates.
- volatility_targeting.csv and strategy_paths/: optional RQ5 with original sigma and costs.
- run_manifest.json: source/output checksums, protocol and method limitations.

FHS uses own-model OOS residuals only after the return is observable. Minimum
20 past residuals is fixed, not selected on evaluation. The early 99% empirical
tail is sparse; inspect n_fhs_tail. No 2026 final holdout is evaluated.
Christoffersen never joins across missing days; gapped-sample p-values are
asymptotic diagnostics. These tests validate VaR coverage, not ES calibration.

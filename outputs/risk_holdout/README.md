# Holdout risk outputs

Final holdout only; see run_manifest.json for exact dates and checksums.
FHS starts with 2021–2025 own-model OOS residuals and adds completed 2026 errors.
Only observable_at <= forecast_available_at and earlier target dates enter the pool.
Strategy starts flat at the beginning of this separate period with the same fixed costs.
Historical named crisis windows are outside this holdout, not new 2026 stress evidence.
Kupiec/Christoffersen test VaR coverage, not ES calibration. At 99%, the short sample
has few expected breaches, so p-values have limited power.

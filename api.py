"""Read-only HTTP API for the current backend's saved research outputs."""

from __future__ import annotations

import json
import math
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
SYMBOLS = {"BTCUSDT", "ETHUSDT"}
MODELS = {
    "combo_core4",
    "combo_econ",
    "enet",
    "garch",
    "gjr_garch",
    "har_rv",
    "hist_mean",
    "naive_rw",
    "xgboost",
}
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "http://127.0.0.1:5173").split(",")
    if origin.strip()
]
SAMPLES = {
    "evaluation": {
        "tables": OUTPUTS / "tables",
        "forecasts": OUTPUTS / "forecasts",
        "risk": OUTPUTS / "risk",
        "evaluation_period": "2021-01-01 to 2025-12-31",
    },
    "holdout": {
        "tables": OUTPUTS / "holdout_tables",
        "forecasts": OUTPUTS / "forecasts_holdout",
        "risk": OUTPUTS / "risk_holdout",
        "evaluation_period": "2026-01-01 to 2026-10-17",
    },
}

app = FastAPI(
    title="Crypto Tail-Risk Forecasting API",
    version="2.0.0",
    description="Read-only API for the current backend's saved evaluation and holdout outputs.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _json_value(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if hasattr(value, "tolist"):
        return _json_value(value.tolist())
    if hasattr(value, "item"):
        return _json_value(value.item())
    if pd.api.types.is_scalar(value) and pd.isna(value):
        return None
    return value


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    return [
        {key: _json_value(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _required_file(path: Path) -> Path:
    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"Required backend output is missing: {path.relative_to(ROOT)}",
        )
    return path


@lru_cache(maxsize=32)
def _read_json(path_string: str) -> dict[str, Any]:
    path = _required_file(Path(path_string))
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=32)
def _read_csv(path_string: str) -> pd.DataFrame:
    return pd.read_csv(_required_file(Path(path_string)))


@lru_cache(maxsize=32)
def _read_parquet(path_string: str) -> pd.DataFrame:
    return pd.read_parquet(_required_file(Path(path_string)))


def _symbol(value: str) -> str:
    result = value.upper()
    if result not in SYMBOLS:
        raise HTTPException(status_code=422, detail="symbol must be BTCUSDT or ETHUSDT")
    return result


def _model(value: str) -> str:
    result = value.lower()
    if result != "best" and result not in MODELS:
        raise HTTPException(status_code=422, detail=f"Unsupported model: {result}")
    return result


def _sample(value: str) -> dict[str, Any]:
    try:
        return SAMPLES[value]
    except KeyError as exc:
        raise HTTPException(
            status_code=422,
            detail="sample must be evaluation or holdout",
        ) from exc


def _window(value: str) -> str:
    if value not in {"rolling", "expanding"}:
        raise HTTPException(status_code=422, detail="window must be rolling or expanding")
    return value


def _horizon(value: int) -> int:
    if value not in {1, 7}:
        raise HTTPException(status_code=422, detail="horizon_days must be 1 or 7")
    return value


def _filtered_table(path: Path, **filters: Any) -> pd.DataFrame:
    frame = _read_csv(str(path))
    for column, value in filters.items():
        if column in frame.columns:
            frame = frame.loc[frame[column].eq(value)]
    return frame


def _forecast_path(files: dict[str, Any], symbol: str, model: str) -> Path:
    return Path(files["forecasts"]) / f"{symbol}_{model}.parquet"


def _risk_path(files: dict[str, Any], symbol: str, model: str) -> Path:
    return Path(files["risk"]) / f"{symbol}_{model}.parquet"


def _best_model(files: dict[str, Any], symbol: str, window: str, horizon_days: int) -> tuple[str, pd.DataFrame]:
    comparison = _filtered_table(
        Path(files["tables"]) / "model_comparison.csv",
        symbol=symbol,
        window=window,
        horizon_days=horizon_days,
    )
    comparison = comparison.dropna(subset=["QLIKE"]).sort_values("QLIKE")
    if comparison.empty:
        raise HTTPException(
            status_code=404,
            detail="No model comparison results exist for the requested filters",
        )
    return str(comparison.iloc[0]["model"]), comparison


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    metadata = _read_json(str(ROOT / "data" / "processed" / "dataset_meta.json"))
    quality = _read_json(str(OUTPUTS / "tables" / "data_quality_summary.json"))
    symbols = quality.get("symbols", [])
    coverage_end = max(
        (row.get("coverage_end_utc", "") for row in symbols),
        default=None,
    )
    return {
        "status": "ok",
        "generated_at": metadata.get("created_at_utc"),
        "data_snapshot": metadata.get("snapshot_id"),
        "dataset_sha256": metadata.get("dataset_sha256"),
        "symbols": sorted(SYMBOLS),
        "data_source": metadata.get("data_source"),
        "market_data_end": coverage_end,
        "evaluation_period": SAMPLES["evaluation"]["evaluation_period"],
        "holdout_period": SAMPLES["holdout"]["evaluation_period"],
        "available_samples": [
            sample
            for sample, files in SAMPLES.items()
            if (Path(files["tables"]) / "model_comparison.csv").is_file()
        ],
    }


@app.get("/api/v1/dashboard/overview")
def overview(
    symbol: str = "BTCUSDT",
    model: str = "best",
    window: str = "rolling",
    horizon_days: int = Query(default=1),
    sample: Literal["evaluation", "holdout"] = "evaluation",
) -> dict[str, Any]:
    symbol, model = _symbol(symbol), _model(model)
    files = _sample(sample)
    window, horizon_days = _window(window), _horizon(horizon_days)
    best_name, comparison = _best_model(files, symbol, window, horizon_days)
    selected_model = best_name if model == "best" else model
    forecast = _read_parquet(str(_forecast_path(files, symbol, selected_model)))
    forecast = forecast.loc[
        forecast["window"].eq(window)
        & forecast["horizon_days"].eq(horizon_days)
        & forecast["status"].eq("ok")
    ].sort_values("origin_date")
    latest_forecast = None if forecast.empty else _records(forecast.tail(1))[0]

    risk = _read_parquet(str(_risk_path(files, symbol, selected_model)))
    risk = risk.loc[risk["window"].eq(window)].sort_values("date")
    latest_risk: dict[str, Any] = {}
    for alpha in (0.05, 0.01):
        rows = risk.loc[risk["alpha"].eq(alpha)]
        key = f"alpha_{int((1 - alpha) * 100)}"
        latest_risk[key] = None if rows.empty else _records(rows.tail(1))[0]

    backtest = _filtered_table(
        Path(files["risk"]) / "backtest.csv",
        coin=symbol,
        model=selected_model,
        window=window,
        sample="common_all_9_models",
    ).sort_values("alpha", ascending=False)
    all_crisis = _filtered_table(
        Path(files["risk"]) / "crisis_breaches.csv",
        coin=symbol,
        window=window,
        alpha=0.01,
        sample="common_all_9_models",
    ).sort_values("start")
    crisis = all_crisis.loc[
        all_crisis["model"].eq(selected_model) & all_crisis["status"].eq("ok")
    ].copy()
    names = {
        "may_2021_selloff": "Bán tháo tháng 5/2021",
        "luna_collapse_2022": "Luna mất neo",
        "ftx_collapse_2022": "Sự kiện FTX",
    }
    if "crisis" in crisis.columns:
        crisis = crisis.assign(
            event=crisis["crisis"].map(names).fillna(crisis["crisis"])
        )
    model_labels = {
        "garch": "GARCH(1,1)",
        "har_rv": "HAR-RV",
        "xgboost": "XGBoost",
    }
    crisis_events = []
    for _, event in crisis.iterrows():
        event_id = str(event["crisis"])
        start, end = str(event["start"])[:10], str(event["end"])[:10]
        event_rows = risk.loc[
            risk["alpha"].eq(0.01)
            & risk["date"].astype(str).str[:10].between(start, end)
        ].sort_values("date")

        log_wealth = 0.0
        peak_log_wealth = 0.0
        max_drawdown_pct = 0.0
        for value in event_rows["return"]:
            if pd.isna(value):
                continue
            log_wealth += float(value) / 100
            peak_log_wealth = max(peak_log_wealth, log_wealth)
            drawdown_pct = (math.exp(log_wealth - peak_log_wealth) - 1) * 100
            max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)

        model_rows = all_crisis.loc[
            all_crisis["crisis"].eq(event_id)
            & all_crisis["status"].eq("ok")
            & all_crisis["model"].isin(model_labels)
        ]
        model_breaches = [
            {
                "model": str(row["model"]),
                "label": model_labels[str(row["model"])],
                "n": _json_value(row["n"]),
                "n_breach": _json_value(row["n_breach"]),
            }
            for _, row in model_rows.iterrows()
        ]
        crisis_events.append(
            {
                **{key: _json_value(value) for key, value in event.items()},
                "max_drawdown_pct": max_drawdown_pct,
                "calendar_days": len(event_rows),
                "model_breaches": model_breaches,
                "series": [
                    {
                        "date": _json_value(row["date"]),
                        "return": _json_value(row["return"]),
                        "var": _json_value(row["var"]),
                        "breach": _json_value(row["breach"]),
                    }
                    for _, row in event_rows.iterrows()
                ],
            }
        )

    dm = _filtered_table(
        Path(files["tables"]) / "dm_vs_benchmark.csv",
        symbol=symbol,
        model=selected_model,
        window=window,
        horizon_days=horizon_days,
        benchmark="har_rv",
        loss="qlike",
    )
    dm_comparison = _filtered_table(
        Path(files["tables"]) / "dm_vs_benchmark.csv",
        symbol=symbol,
        window=window,
        horizon_days=horizon_days,
        benchmark="har_rv",
        loss="qlike",
    ).set_index("model")
    comparison = comparison.copy()
    comparison["dm_p_value"] = comparison["model"].map(dm_comparison["p_value"])
    comparison["dm_mean_diff"] = comparison["model"].map(dm_comparison["mean_diff"])
    comparison["dm_status"] = comparison["model"].map(dm_comparison["status"])
    dataset = _read_parquet(str(ROOT / "data" / "processed" / "dataset.parquet"))
    symbol_data = dataset.loc[dataset["symbol"].eq(symbol)].sort_values("origin_date")
    latest_market = None
    forecast_regime = None
    if latest_forecast is not None:
        origin = symbol_data.loc[
            symbol_data["origin_date"].eq(latest_forecast["origin_date"])
        ]
        if not origin.empty:
            latest_market = _records(origin.tail(1))[0]
            forecast_regime = _json_value(origin.iloc[-1].get("regime"))
    elif not symbol_data.empty:
        latest_market = _records(symbol_data.tail(1))[0]
    quality = _read_json(str(OUTPUTS / "tables" / "data_quality_summary.json"))
    coin_quality = next(
        (row for row in quality.get("symbols", []) if row.get("symbol") == symbol),
        {},
    )
    if latest_market is not None and latest_market.get("rv_d") is not None:
        latest_market["realized_volatility_pct"] = float(
            max(latest_market["rv_d"], 0) ** 0.5
        )
    best_rows = comparison.loc[comparison["model"].eq(best_name)]

    return {
        "symbol": symbol,
        "model": selected_model,
        "window": window,
        "horizon_days": horizon_days,
        "sample": sample,
        "snapshot_id": _read_json(
            str(ROOT / "data" / "processed" / "dataset_meta.json")
        ).get("snapshot_id"),
        "evaluation_period": files["evaluation_period"],
        "market_data_end": coin_quality.get("coverage_end_utc"),
        "latest_forecast": latest_forecast,
        "forecast_origin_regime": forecast_regime,
        "latest_risk": latest_risk,
        "latest_market": latest_market,
        "best_model": None if best_rows.empty else _records(best_rows.head(1))[0],
        "comparison": _records(comparison),
        "risk_backtest": _records(backtest),
        "crisis_backtest": crisis_events,
        "qlike_dm_vs_har": None if dm.empty else _records(dm.head(1))[0],
    }


@app.get("/api/v1/market")
def market(
    symbol: str = "BTCUSDT",
    limit: int = Query(default=180, ge=1, le=3000),
) -> dict[str, Any]:
    symbol = _symbol(symbol)
    dataset = _read_parquet(str(ROOT / "data" / "processed" / "dataset.parquet"))
    data = dataset.loc[dataset["symbol"].eq(symbol)].sort_values("origin_date").tail(limit)
    quality = _read_json(str(OUTPUTS / "tables" / "data_quality_summary.json"))
    coin_quality = next(
        (row for row in quality.get("symbols", []) if row.get("symbol") == symbol),
        {},
    )
    columns = [
        column
        for column in (
            "origin_date",
            "origin_segment",
            "regime",
            "rv_d",
            "rv_w",
            "rv_m",
            "ret_d",
            "regime_rv22_pct2",
            "target_end_h1",
            "target_end_h7",
            "y_rv_h1",
            "y_rv_h7",
        )
        if column in data.columns
    ]
    return {
        "symbol": symbol,
        "quality": coin_quality,
        "series": _records(data[columns]),
    }


@app.get("/api/v1/forecasts")
def forecasts(
    symbol: str = "BTCUSDT",
    model: str = "combo_core4",
    window: str = "rolling",
    horizon_days: int = Query(default=1),
    limit: int = Query(default=500, ge=1, le=3000),
    sample: Literal["evaluation", "holdout"] = "evaluation",
) -> dict[str, Any]:
    symbol, model = _symbol(symbol), _model(model)
    files = _sample(sample)
    window, horizon_days = _window(window), _horizon(horizon_days)
    if model == "best":
        model, _ = _best_model(files, symbol, window, horizon_days)
    frame = _read_parquet(str(_forecast_path(files, symbol, model)))
    frame = frame.loc[
        frame["window"].eq(window) & frame["horizon_days"].eq(horizon_days)
    ].sort_values("origin_date").tail(limit)
    return {
        "symbol": symbol,
        "model": model,
        "window": window,
        "horizon_days": horizon_days,
        "sample": sample,
        "count": len(frame),
        "items": _records(frame),
    }


@app.get("/api/v1/research/volatility")
def volatility_research(
    symbol: str = "BTCUSDT",
    window: str = "rolling",
    horizon_days: int = Query(default=1),
    sample: Literal["evaluation", "holdout"] = "evaluation",
) -> dict[str, Any]:
    symbol = _symbol(symbol)
    files = _sample(sample)
    window, horizon_days = _window(window), _horizon(horizon_days)

    def table(name: str) -> list[dict[str, Any]]:
        path = Path(files["tables"]) / name
        if not path.is_file():
            return []
        frame = _read_csv(str(path))
        for column, value in (
            ("symbol", symbol),
            ("window", window),
            ("horizon_days", horizon_days),
        ):
            if column in frame.columns:
                frame = frame.loc[frame[column].eq(value)]
        return _records(frame)

    return {
        "symbol": symbol,
        "window": window,
        "horizon_days": horizon_days,
        "sample": sample,
        "volume_ablation": table("backend3_volume_ablation.csv"),
        "macro_sensitivity": table("backend3_macro_ablation.csv"),
        "shap_importance": table("backend3_shap_importance.csv"),
        "regime_performance": table("regime_performance.csv"),
        "regime_counts": table("regime_counts.csv"),
    }


@app.get("/api/v1/risk")
def risk(
    symbol: str = "BTCUSDT",
    model: str = "combo_core4",
    window: str = "rolling",
    alpha: float = Query(default=0.05),
    limit: int = Query(default=500, ge=1, le=3000),
    sample: Literal["evaluation", "holdout"] = "evaluation",
) -> dict[str, Any]:
    symbol, model = _symbol(symbol), _model(model)
    files = _sample(sample)
    window = _window(window)
    if alpha not in {0.01, 0.05}:
        raise HTTPException(status_code=422, detail="alpha must be 0.01 or 0.05")
    if model == "best":
        model, _ = _best_model(files, symbol, window, 1)
    frame = _read_parquet(str(_risk_path(files, symbol, model)))
    frame = frame.loc[
        frame["window"].eq(window) & frame["alpha"].eq(alpha)
    ].sort_values("date").tail(limit)
    return {
        "symbol": symbol,
        "model": model,
        "window": window,
        "alpha": alpha,
        "sample": sample,
        "count": len(frame),
        "items": _records(frame),
    }


@app.get("/api/v1/risk/research")
def risk_research(
    symbol: str = "BTCUSDT",
    model: str = "combo_core4",
    window: str = "rolling",
    alpha: float = Query(default=0.01),
    sample: Literal["evaluation", "holdout"] = "evaluation",
) -> dict[str, Any]:
    symbol, model = _symbol(symbol), _model(model)
    files = _sample(sample)
    window = _window(window)
    if alpha not in {0.01, 0.05}:
        raise HTTPException(status_code=422, detail="alpha must be 0.01 or 0.05")

    risk_dir = Path(files["risk"])
    backtest = _filtered_table(
        risk_dir / "backtest.csv",
        coin=symbol,
        window=window,
        alpha=alpha,
        sample="common_all_9_models",
    ).sort_values("quantile_loss")
    crises = _filtered_table(
        risk_dir / "crisis_breaches.csv",
        coin=symbol,
        window=window,
        alpha=alpha,
        sample="common_all_9_models",
    ).sort_values(["start", "crisis", "model"])
    strategies = _filtered_table(
        risk_dir / "volatility_targeting.csv",
        coin=symbol,
        window=window,
    ).sort_values("strategy_sharpe", ascending=False)

    strategy_path = risk_dir / "strategy_paths" / f"{symbol}_{model}_{window}.parquet"
    series: list[dict[str, Any]] = []
    if strategy_path.is_file():
        strategy = _read_parquet(str(strategy_path)).sort_values("date")
        columns = [
            column
            for column in (
                "date",
                "strategy_cum",
                "bh_cum",
                "sigma_pct",
                "forecast_used",
                "weight",
                "cost_pct",
            )
            if column in strategy.columns
        ]
        series = _records(strategy[columns].tail(3000))

    selected_strategy = strategies.loc[strategies["model"].eq(model)]
    return {
        "symbol": symbol,
        "model": model,
        "window": window,
        "alpha": alpha,
        "sample": sample,
        "backtest": _records(backtest),
        "crisis_backtest": _records(crises),
        "volatility_targeting": _records(strategies),
        "selected_strategy": None if selected_strategy.empty else _records(selected_strategy.head(1))[0],
        "strategy_series": series,
    }


@app.get("/api/v1/exports/dashboard.csv")
def export_dashboard(
    symbol: str = "BTCUSDT",
    window: str = "rolling",
    horizon_days: int = Query(default=1),
    sample: Literal["evaluation", "holdout"] = "evaluation",
) -> Response:
    symbol = _symbol(symbol)
    files = _sample(sample)
    window, horizon_days = _window(window), _horizon(horizon_days)
    model, _ = _best_model(files, symbol, window, horizon_days)
    forecast = _read_parquet(str(_forecast_path(files, symbol, model)))
    forecast = forecast.loc[
        forecast["window"].eq(window) & forecast["horizon_days"].eq(horizon_days)
    ]
    risk_frame = _read_parquet(str(_risk_path(files, symbol, model)))
    risk_frame = risk_frame.loc[
        risk_frame["window"].eq(window) & risk_frame["alpha"].isin([0.01, 0.05])
    ]
    columns = [
        column
        for column in ("date", "alpha", "return", "var", "es", "breach", "status")
        if column in risk_frame.columns
    ]
    risk_frame = risk_frame[columns].copy()
    risk_frame["risk_level"] = risk_frame["alpha"].map({0.05: "95", 0.01: "99"})
    risk_frame = risk_frame.pivot(
        index="date",
        columns="risk_level",
        values=["var", "es", "breach"],
    )
    risk_frame.columns = [
        f"{measure}_{level}" for measure, level in risk_frame.columns
    ]
    risk_frame = risk_frame.reset_index()
    export = forecast.merge(
        risk_frame,
        left_on="target_date",
        right_on="date",
        how="left",
    )
    filename = f"{symbol}_{model}_{window}_{sample}_h{horizon_days}_dashboard.csv"
    return Response(
        content=export.to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%SZ"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/v1/methodology")
def methodology() -> dict[str, Any]:
    metadata = _read_json(str(ROOT / "data" / "processed" / "dataset_meta.json"))
    quality = _read_json(str(OUTPUTS / "tables" / "data_quality_summary.json"))
    backend_validation = _read_json(
        str(OUTPUTS / "tables" / "backend1_validation.json")
    )
    risk_validation_path = OUTPUTS / "risk" / "verification.json"
    risk_validation = (
        _read_json(str(risk_validation_path)) if risk_validation_path.is_file() else {}
    )
    pipeline_path = OUTPUTS / "final_holdout_pipeline.json"
    pipeline = _read_json(str(pipeline_path)) if pipeline_path.is_file() else {}
    quality_by_symbol = {
        row["symbol"]: row
        for row in quality.get("symbols", [])
        if row.get("symbol") in SYMBOLS
    }
    source_quality = [
        {
            "symbol": symbol,
            "raw_rows": row.get("raw_rows"),
            "clean_rows": row.get("clean_rows"),
            "coverage_start_utc": row.get("coverage_start_utc"),
            "coverage_end_utc": row.get("coverage_end_utc"),
            "expected_days": row.get("expected_days"),
            "days_eligible_rv": row.get("days_eligible_rv"),
            "incomplete_days": row.get("incomplete_days"),
            "missing_bars": row.get("missing_bars"),
            "zero_volume_bars": row.get("zero_volume_bars"),
            "large_return_bars": row.get("large_return_bars"),
            "daily_quality_by_segment": row.get("daily_quality_by_segment", []),
        }
        for symbol, row in sorted(quality_by_symbol.items())
    ]
    return {
        "assets": sorted(SYMBOLS),
        "data_frequency": "5-minute spot candles, aggregated to daily UTC features",
        "snapshot_id": metadata.get("snapshot_id"),
        "data_source": metadata.get("data_source"),
        "dataset_sha256": metadata.get("dataset_sha256"),
        "protocol_sha256": metadata.get("protocol_sha256"),
        "dataset_rows": metadata.get("rows"),
        "feature_columns": metadata.get("feature_columns", []),
        "target_7d_aggregation": metadata.get("target_7d_aggregation"),
        "missing_data_policy": metadata.get("missing_data"),
        "turnover_is_proxy": metadata.get("turnover_is_proxy"),
        "evaluation_period": SAMPLES["evaluation"]["evaluation_period"],
        "holdout": SAMPLES["holdout"]["evaluation_period"],
        "models": sorted(MODELS),
        "core_models": ["har_rv", "garch", "gjr_garch", "xgboost"],
        "source_quality": source_quality,
        "macro_sources": quality.get("macro", []),
        "crosscheck": quality.get("crosscheck", []),
        "study_protocol": quality.get("study_protocol", {}),
        "backend_validation": {
            "status": backend_validation.get("status"),
            "forecast_rows": backend_validation.get("forecast_rows"),
            "common_scored_rows": backend_validation.get("common_scored_rows"),
            "holdout_scored": backend_validation.get("holdout_scored"),
        },
        "risk_validation": {
            "status": risk_validation.get("check"),
            "tests": risk_validation.get("unit_tests", {}).get("tests"),
            "passed": risk_validation.get("unit_tests", {}).get("passed"),
            "failures": risk_validation.get("unit_tests", {}).get("failures"),
            "errors": risk_validation.get("unit_tests", {}).get("errors"),
        },
        "holdout_pipeline_state": pipeline.get("state"),
        "repository_url": "https://github.com/thanhnha39/Crypto-Tail-Risk-Volatility-Forecasting-Engine",
        "forecast_units": {
            "rv_forecast_pct2": "% squared",
            "volatility_forecast_pct": "%",
        },
        "risk_units": {
            "return": "percent log return",
            "var": "left-tail percent log return",
            "es": "left-tail percent log return",
        },
        "risk_notes": [
            "VaR/ES remain left-tail returns and are usually negative.",
            "A breach occurs when realized return is below VaR.",
            "Unavailable values remain null; they are not replaced with zero.",
            "The evaluation sample (2021-2025) and final holdout (2026) are served separately.",
            "Kupiec and Christoffersen backtests assess VaR coverage, not ES calibration.",
            "Macro series are excluded from the main model because point-in-time availability is not verified.",
            "The final holdout ends on 2026-10-17 and has limited power for 99% VaR tests.",
        ],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000)

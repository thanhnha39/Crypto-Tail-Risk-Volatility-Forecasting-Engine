# Crypto Tail-Risk & Volatility Forecasting Engine — Frontend

Five-tab dashboard for Tổng quan, Dữ liệu & trạng thái thị trường, Dự báo biến động, VaR & giá trị kinh tế, and Phương pháp & giới hạn.

## Run locally (PowerShell)

Set up the read-only API environment once:

```powershell
npm run setup:api
```

Start the API and frontend in separate terminals:

```powershell
npm run dev:api
npm run dev
```

Open `http://127.0.0.1:5173`. Interactive API docs are at
`http://127.0.0.1:8000/docs`.

`npm run dev` is pinned to `http://127.0.0.1:5173`; if the port is occupied,
Vite exits with an error instead of silently switching to another port.
`npm run dev:api` uses the project's `.venv-api` and safely restarts an older
instance of this same API before binding port 8000. It will not stop an
unrelated process that happens to use that port. If the API code changes,
rerun `npm run dev:api` in a new terminal; the old server will be replaced
automatically. Only `http://127.0.0.1:5173` is allowed by API CORS.
For hosted deployment, set `VITE_API_BASE_URL` to the public API URL in the
frontend hosting environment and configure the backend's `FRONTEND_ORIGINS`
environment variable to the exact public frontend origin(s), comma-separated.

The API serves precomputed output files from the backend clone in `backend/`;
it does not download data, fit models, or modify research outputs. Restart the
API after changing backend API code or output files so the server reloads the
code and refreshes its in-memory file cache.

## API routes

- `GET /api/v1/health`
- `GET /api/v1/dashboard/overview`
- `GET /api/v1/market`
- `GET /api/v1/forecasts`
- `GET /api/v1/research/volatility`
- `GET /api/v1/risk`
- `GET /api/v1/risk/research`
- `GET /api/v1/methodology`
- `GET /api/v1/exports/dashboard.csv`

Forecast, overview, research, risk, and CSV export routes accept
`sample=evaluation` (default) or `sample=holdout`. The dashboard currently
opens the main 2021–2025 evaluation sample. Configure a different API base URL
with `VITE_API_BASE_URL` in `.env.local`; by default it uses
`http://127.0.0.1:8000/api/v1`.

The overview response includes historical crisis-window VaR 99% breaches,
daily return/VaR chart points, GARCH/HAR-RV/XGBoost comparisons, and maximum
drawdown for available evaluation windows. The 2021–2022 crisis windows are
outside the 2026 holdout period and are not presented as holdout results.
RQ1 model comparisons also include per-model Diebold-Mariano p-values against
HAR-RV; its rolling QLIKE chart is calculated from paired forecast and observed
RV values for the selected symbol, horizon, and sample.
RQ2 displays the backend's paired volume ablation and TreeSHAP feature
importance. Macro sensitivity remains separate from the main model results,
and absent holdout artifacts are shown as unavailable rather than filled with
evaluation values.

## Stack

- React, TypeScript, Vite
- TanStack Query and Axios for API requests and server state
- Recharts for charts
- FastAPI and Uvicorn for the read-only adapter
- Lucide React for icons

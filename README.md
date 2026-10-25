# Crypto Tail-Risk & Volatility Forecasting Engine — Frontend

Five-tab dashboard for Tổng quan, Dữ liệu & trạng thái thị trường, Dự báo biến động, VaR & giá trị kinh tế, and Phương pháp & giới hạn.

## Run locally (PowerShell)

Install the small HTTP adapter environment once:

```powershell
npm run setup:api
```

Start the backend API in one terminal, then start the frontend in another:

```powershell
npm run dev:api
npm run dev
```

Open `http://127.0.0.1:5173`. FastAPI docs are available at `http://127.0.0.1:8000/docs`.

## API routes

- `GET /api/v1/health`
- `GET /api/v1/dashboard/overview`
- `GET /api/v1/market`
- `GET /api/v1/forecasts`
- `GET /api/v1/risk`
- `GET /api/v1/methodology`
- `GET /api/v1/exports/dashboard.csv`

The read-only adapter in `backend/api.py` serves the precomputed Parquet, CSV, and JSON research outputs from the cloned backend repository. It does not refit models. The clone uses a sparse checkout of source, docs, configuration, processed dataset, and outputs. The API host can be changed with `VITE_API_BASE_URL` (see `.env.example`).

## Stack

- React, TypeScript, Vite
- TanStack Query and Axios for server state and HTTP
- Recharts for charts
- Lucide React for icons
- FastAPI and Uvicorn for the local API adapter

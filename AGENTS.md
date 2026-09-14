# NOPIS Agent Guide

NOPIS is a Milan telecom network-operations system. It combines a PySpark batch ETL pipeline, a MySQL warehouse, a FastAPI service, ML risk prediction, and a Vite/React dashboard.

## Working Rules

- Treat [spark/JOB_CONTRACT.md](spark/JOB_CONTRACT.md) and [docs/predict_risk_contract.md](docs/predict_risk_contract.md) as the canonical pipeline and prediction API contracts. Update implementations and tests together when a contract changes.
- Preserve the pipeline order: `process_landing()` -> `read_raw()` -> `clean()` -> `aggregate()` -> `enrich()` -> `write_outputs()`.
- Keep failure behavior atomic: on ingestion, Spark, aggregation, or other pipeline failure, do not leave partial processed or analytics outputs. Run the focused tests before broad changes.
- Use the package entry point `python -m spark.telecom_pipeline` for the current pipeline. Older scripts under `Phase_2/` are historical/educational and may use hard-coded paths.
- The current Spark setup is Windows-oriented. Check [spark/spark_session.py](spark/spark_session.py) before changing runtime paths, `winutils`, temporary directories, or timezone behavior.
- Do not mix the unified pipeline's `data/processed` and `data/analytics` outputs with the older `spark/output` contract without explicitly reconciling the paths.
- API changes belong in the router, service, and Pydantic schema layers together. Use inclusive `from_dt`/`to_dt` range semantics for summary queries and preserve documented validation/status behavior.
- The API requires MySQL and the ML artifacts under `ml/` at startup. Keep connection timeouts and graceful database-error handling intact so an unavailable database cannot hang requests indefinitely.
- Frontend API calls belong in [Phase_5/src/api/config.js](Phase_5/src/api/config.js); use `VITE_API_BASE_URL` and keep static map data available under `Phase_5/public`.
- Prefer focused edits and tests. Do not commit changes unless explicitly asked.

## Validation Commands

From the repository root:

```powershell
python -m pytest tests/test_pipeline_91_92.py -v
python -m spark.telecom_pipeline
```

For the dashboard:

```powershell
Set-Location Phase_5
npm run build
npm run dev
```

There is currently no frontend test or lint script. API tests are under [Phase_4/tests](Phase_4/tests). Review [Phase_3/de1_telco_data_arch.txt](Phase_3/de1_telco_data_arch.txt) for the broader architecture and [Phase_3/de_5_storage_strat.txt](Phase_3/de_5_storage_strat.txt) for storage semantics.

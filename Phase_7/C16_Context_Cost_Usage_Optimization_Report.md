# C16 - Context, Cost & Usage Optimization

## 1. Objective

Compare a raw multi-grid context design with a small, evidence-grounded context design for:

> Which grids need operational attention right now, and why?

This is a read-only comparison experiment. It does not create a production API or agent, and it does not send the raw warehouse extract to a model. Spark and SQL remain responsible for filtering, aggregation, and selection.

## 2. Project Data Used

The experiment ran on the local MySQL warehouse on 2026-09-06.

| Source | Actual rows | Use |
|---|---:|---|
| `fact_network_activity` | 1,679,994 | Raw canonical hourly activity rows |
| `dim_grid` | 10,000 | Grid registry |
| `dim_time` | 168 | Hourly time dimension |
| `network_anomaly_scores` | 1,556,206 | Statistical anomaly evidence |
| `grid_features` | 9,998 | Stored feature vectors |
| `network_risk_scores` | 1,559,994 | Stored risk snapshots |

The raw activity range was 2013-11-01 00:00:00 through 2013-11-07 23:00:00, covering 10,000 grids and 168 hourly slots. The canonical grain is one grid per hourly timestamp after country-code aggregation.

Existing API mappings used as the source-contract reference were:

- `GET /network/summary`
- `GET /network/grid/{grid_id}`
- `GET /network/hotspots`
- `GET /network/alerts`
- `GET /network/grid/{grid_id}/features`
- `GET /network/grid/{grid_id}/evidence`
- `GET /network/pipeline/status`

The experiment queried the corresponding warehouse tables directly for reproducible measurement because the API server was not required for this offline comparison. No business logic was copied into production code.

Pipeline evidence from the existing ingestion log was `DEGRADED`: 20 valid ingestions, 1 invalid ingestion, and 0 rejected files.

## 3. Design A - Raw Context

### Context sent in the safe experiment

A representative 100-row sample was selected from `fact_network_activity JOIN dim_time`. Each sample record contained grid ID, timestamp, total activity, internet share, total SMS, and total calls. This sample was used for a safe local answer exercise only.

Measured raw row count: **1,679,994**.

### Context-size calculation

The compact JSON sample measured:

- 16,091 serialized characters
- 16,091 bytes
- 4,023 estimated tokens using the transparent approximation `characters / 4`

Scaling that measured sample to all 1,679,994 rows gives:

- **270,327,835 estimated serialized characters**
- **67,586,159 estimated tokens**

The full figure is an estimate, not a tokenizer measurement. It is included to show why the full raw extract should not be sent to a model.

Observed database timing for the 100-row safe sample query: **16,356.216 ms**. This includes local database access and is not model latency.

### Answer produced by the experiment

> The safe raw experiment sample contains 100 rows out of 1,679,994 measured rows. Its largest observed proportional activity value is grid 48 at 2013-11-01 00:00:00 with `total_activity=944.5690000000002`. This is sample-only evidence, not a complete attention ranking.

### Assessment

The answer is honest about the sample boundary, but it cannot reliably answer which grids need attention across the full network. A sample maximum is not a network-wide ranking.

## 4. Design B - Curated Context

### Selection

SQL selected the 10 highest anomaly scores at the latest anomaly timestamp, 2013-11-07 17:30:00. For each selected grid, the package included:

- anomaly current value, baseline, deviation, score, direction, and reason;
- latest activity at or before the anomaly timestamp;
- latest stored feature vector and its feature timestamp;
- latest stored risk snapshot, risk level, and model version;
- pipeline status as package-level evidence.

The package contained **10 grid evidence records**, which is within the requested 10-20 record range. All 10 selected records had anomaly, activity, feature, and risk values present. The feature timestamp was 2013-11-03 17:30:00, older than the anomaly timestamp, so this freshness limitation is explicitly retained.

### Context size and latency

The serialized curated package measured:

- 9,463 characters
- 9,463 bytes
- **2,366 estimated tokens** using the same `characters / 4` approximation

Observed curated evidence query timing: **7,693.801 ms**, excluding model latency.

The full raw estimate is approximately **28,566 times larger** than the curated package by estimated tokens.

### Answer produced by the experiment

> At anomaly timestamp 2013-11-07 17:30:00, the curated package identifies 10 grids with HIGH anomaly direction: 6572, 1543, 7721, 6477, 6478, 6479, 2780, 9068, 4480, 1844. The reasons are the observed current-versus-baseline activity and anomaly scores in each record. Pipeline status and feature/risk timestamps must be checked before treating this as a complete current assessment.

The answer is evidence-grounded, names the selected grids, keeps the anomaly timestamp visible, and carries forward the degraded pipeline and stale feature context as limitations.

## 5. Comparison

| Measure | Design A: raw context | Design B: curated context |
|---|---|---|
| Records | 100 safe sample; 1,679,994 measured full rows | 10 grid records plus package metadata |
| Context size | 4,023 estimated sample tokens; 67,586,159 estimated full tokens | 2,366 estimated tokens |
| Answer quality | Low for ranking; sample-only | Higher for triage; selected evidence is directly relevant |
| Relevance | Many unrelated hourly grid records | High; records selected by latest anomaly score |
| Observed data query latency | 16,356.216 ms for safe sample query | 7,693.801 ms for curated evidence queries |
| Model latency | Not measured; no model request made | Not measured; no model request made |
| Cost implication | Very high token usage if full estimate were sent | Much lower token usage; exact provider cost not assumed |
| Unnecessary information | Most rows are unrelated to the question | Limited; source timestamps and package metadata remain useful |
| Uncertainty handling | Clearly sample-limited, but cannot rank the network | Carries degraded pipeline status and stale feature timestamp |
| Reliability | Weak for network-wide attention decisions | Stronger for focused triage, but dependent on source freshness |

These are measured data-access and serialization results. No model billing, model response latency, or external price was claimed because no model request was made during the experiment.

## 6. What Each Design Does Better or Worse

### Design A strengths

- Preserves broad raw coverage.
- Allows a later SQL or Spark process to recompute different rankings.
- Retains detailed hourly records for offline validation.

### Design A weaknesses

- The full estimate is too large for practical model context use.
- A safe sample does not answer a network-wide ranking question.
- Irrelevant rows dilute attention and increase processing time and token usage.
- The model would be asked to perform work that belongs in Spark or SQL.

### Design B strengths

- Fits the question directly with 10 selected records.
- Preserves source timestamps, anomaly reasons, feature freshness, and risk metadata.
- Makes uncertainty visible instead of hiding the degraded pipeline state.
- Reduces context size by roughly 28,566 times relative to the full raw estimate.

### Design B weaknesses

- Selection depends on the existing anomaly ordering and latest timestamp.
- It can miss a grid whose anomaly data is missing or delayed.
- Features are older than the selected anomaly timestamp in this dataset.
- It is a decision-support package, not a replacement for warehouse validation.

## 7. Model Selection Guidelines

### Use a cheaper/faster model for

- Formatting an already-curated evidence package into the standard investigation brief.
- Extracting claims with `source_tool` or source-table references.
- Summarizing `/network/summary`, `/network/hotspots`, and `/network/alerts` when the evidence is complete.
- Producing short operator handoff notes after SQL has selected the relevant records.
- Checking whether required output fields are present.

### Use a deeper reasoning model for

- Reconciling disagreement between anomaly direction, stored risk level, features, and rule alerts.
- Explaining why evidence is insufficient or temporally stale.
- Reviewing a multi-stage pipeline change across Spark, warehouse, API, and dashboard contracts.
- Comparing competing incident hypotheses when several source signals disagree.
- Producing a careful engineering or operational review where uncertainty and contract impact must be separated.

The model should not be selected to perform large-scale filtering, grouping, duplicate detection, or feature computation. Those operations belong in Spark, SQL, or the existing API services.

## 8. Long-Session Context Management

- Start each investigation with a compact scope summary: grid IDs, `as_of` timestamp, pipeline status, and source freshness.
- Keep raw records outside the model context and retain only the SQL/Spark-selected evidence needed for the current question.
- After each investigation stage, summarize confirmed observations, unresolved questions, and source timestamps.
- Compact completed tool outputs into a structured evidence ledger rather than carrying repeated raw JSON forward.
- Preserve provenance fields such as source endpoint/table, `grid_id`, `feature_timestamp`, and `as_of`.
- Never compact away uncertainty, missing sources, failed calls, or stale timestamps.
- When the question changes, discard irrelevant evidence and query a new curated package instead of appending indefinitely.
- Use a deeper model for the final synthesis only when cross-source disagreement or uncertainty requires it.

## 9. Final Project Context and Cost Rules

1. Spark and SQL perform large-scale computation, aggregation, filtering, ranking, and duplicate checks.
2. LLM context contains curated evidence, not millions of raw hourly rows.
3. Use the canonical grain: one grid per hourly timestamp after country-code aggregation.
4. Activity values are proportional activity measures, not counts or MB.
5. High activity is reported as elevated or high activity only; it is not a capacity conclusion.
6. Every measured value includes a source and relevant timestamp where available.
7. Estimated token counts must be labelled as estimates and must not be presented as tokenizer measurements.
8. Pipeline health and evidence freshness must be included in uncertainty handling.
9. Use the cheapest model that can perform the bounded task; reserve deeper reasoning for disagreement, temporal uncertainty, and cross-layer review.
10. Do not claim model cost or latency without measuring the request or citing an explicit provider price.
11. Compact long sessions by retaining decisions, evidence references, unresolved uncertainty, and next checks.
12. Do not add a new API or production agent solely to optimize context; reuse existing endpoints and warehouse tables.

## 10. Conclusion

Design B is the better operational context design for this question. It reduced the estimated context from 67,586,159 tokens for the full raw extract to 2,366 estimated tokens while producing a more relevant answer about 10 selected grids and preserving uncertainty. Design A remains valuable before model use for broad offline analysis and validation, but its large raw output should be reduced by Spark or SQL first.

The experiment was read-only and did not send either design to a paid model. The recorded answer comparison is therefore a deterministic evidence-package comparison, not a benchmark of model-generated prose. Future benchmarking can send the same two packages to approved models after defining a provider, price, latency measurement method, and independent answer-quality rubric.

## Files

- `Phase_7/c16_context_cost_experiment.py` - read-only measurement and comparison code.
- `Phase_7/c16_context_cost_results.json` - measured counts, package, answers, sizes, and timings.
- `Phase_7/C16_Context_Cost_Usage_Optimization_Report.md` - this report.

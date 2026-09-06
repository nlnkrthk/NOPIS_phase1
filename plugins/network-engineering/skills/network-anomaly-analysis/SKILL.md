<!-- 299. Package them into a project or team plugin. -->
---
name: network-anomaly-analysis
description: Analyze telecom grid anomalies, unexpected traffic surges, and operational alert triggers using NOPIS domain standards.
version: 1.0.0
---

# Network Anomaly Analysis Skill

This skill governs how Claude analyzes and interprets anomalous activity and operational alerts for geographic cells in the NOPIS Milan telecom network.

## Activation Criteria

### Activates On:
- "Why is a grid flagged?"
- "Why is Grid <ID> unusual / anomalous?"
- "What does an anomaly score mean?"
- "Is this activity pattern unusual?"
- "Why did the anomaly detector flag this grid?"
- Any triage request regarding grid-level telemetry deviations or alerts.

### Does NOT Activate On:
- Pipeline failures, Spark crashes, or ingestion issues (use `pipeline-troubleshooting`).
- Grain validation, duplicate records, or GeoJSON join debugging (use `telecom-data-quality`).
- General API routing questions or code maintenance.
- Bare grid IDs with no question or context (e.g., just "Grid 4821") — the skill insists on evidence.

---

## Required Evidence Checklist

Before producing a valid severity assessment, the following evidence must be verified:
1. **Current Activity**: Observed total activity, internet share, SMS/call breakdown.
2. **Baseline Activity**: Historical median activity for this same hour-of-day.
3. **Statistical Anomaly Score**: Percentage deviation from baseline (`(current - baseline) / baseline * 100`) and direction (`HIGH`, `NORMAL`, `LOW`).
4. **Rule-Based Alerts**: Active threshold alerts from `/network/alerts` (`alert_type`, `severity`).
5. **ML Classifier Risk**: Probability risk score and risk level (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
6. **Pipeline Quality Status**: Confirmation from `dim_time` that data is fresh (`VALID`, not `STALE`).

> [!IMPORTANT]
> **Domain Rule — Insufficient Evidence**:
> If required evidence is missing or incomplete, do **NOT** invent metrics, guess, or assign an unsupported severity.
> You must assign `SEVERITY: INSUFFICIENT EVIDENCE` and prompt the user to collect evidence via:
> `/explain-grid <grid_id>` or `/review-anomaly <grid_id>`.

---

## Non-Negotiable NOPIS Terminology & Domain Rules

1. **Proportional Activity Units**: Activity values are relative activity measures derived from telecom interaction intensities. **Never label or convert them to counts, calls, users, or megabytes (MB)**.
2. **Never Claim Confirmed Congestion**: High activity reflects observed traffic intensity, **not confirmed congestion**. Confirmed congestion requires RAN/PRB utilization, queue drops, and radio interface telemetry not present in this dataset.
3. **Grid is a Geographic Cell**: A grid is a **square geographic cell** (1–10,000 in the Milan grid), **never a cell tower, base station, or eNodeB**.
4. **Strict Separation of Evidence & Interpretation**:
   - `EVIDENCE`: Strict recitation of observed numerical values and database facts.
   - `INTERPRETATION`: Analytical reasoning, baseline context, and contextual synthesis.

---

## Mandatory Response Structure

All anomaly investigations must strictly use these four sections:

```text
SEVERITY:
[NORMAL | ELEVATED | CRITICAL | INSUFFICIENT EVIDENCE]

EVIDENCE:
- Coordinates: <Lon, Lat>
- Timestamp: <ISO datetime>
- Observed Total Activity: <value> (Proportional activity units)
- Internet Activity / Share: <value> (<percentage>%)
- Total SMS / Total Calls: <sms> / <calls>
- Historical Baseline: <value> (Median for this hour)
- Anomaly Score: <value>% (<direction>)
- Rule-Based Alert: <ACTIVE (type, severity) | NO ALERT>
- ML Classifier Risk: <score> (<level>)
- Pipeline Freshness: <VALID | STALE>

INTERPRETATION:
- Comparison between current activity and historical median baseline.
- Analysis of signal convergence (rule alerts vs. ML model vs. statistical baseline).
- Explicit reminder: Activity values represent proportional telemetry intensity, NOT confirmed congestion or capacity overload.

NEXT CHECKS:
1. Compare against neighboring grids in the cluster to determine localized vs. sector-wide phenomena.
2. Verify OMC/RAN drop and blocking counters before operational field dispatch.
3. Run /review-anomaly to verify signal consensus across models.
```

<!-- 299. Package them into a project or team plugin. -->
---
description: Gather activity, features, anomalies, and location to produce an operational incident explanation (NOC-oriented)
---

# /explain-grid

Provides a 4-section structured incident investigation for a specific grid cell: `SEVERITY`, `EVIDENCE`, `INTERPRETATION`, and `NEXT CHECKS`.

## Usage
```text
/explain-grid <grid_id> [as_of]
```

### Example
```text
/explain-grid 4821
```

## Behind the Scenes
Executes:
```bash
python Phase_7/c_tasks/project_commands.py explain-grid $1 $2
```

## Rules & Constraints
- **Do NOT claim confirmed congestion**: Telemetry represents proportional activity, not confirmed congestion or capacity exhaustion.
- **Separate Evidence from Interpretation**: Present observed numbers first, followed by analytical deduction.
- **Four Standard Sections**:
  1. `SEVERITY` (NORMAL, ELEVATED, or CRITICAL)
  2. `EVIDENCE` (Observed activity, coordinates, ML2 features, baseline deviation)
  3. `INTERPRETATION` (Contextual analysis of trends)
  4. `NEXT CHECKS` (Prescribed triage steps for NOC engineers)

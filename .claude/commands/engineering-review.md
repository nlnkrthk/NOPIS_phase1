---
description: Run tests first, then perform a six-category advisory engineering review of the current Git diff
---

# /engineering-review

Perform a read-only engineering review of the current NOPIS working-tree change. This command is advisory only. Do not modify files, approve, merge, commit, push, deploy, or change production systems.

<!-- C15 - Headless / CI Engineering Review for this Network Operations & Predictive Intelligence repository. -->

## Required order

Always follow this order:

1. Read `CLAUDE.md` first. Treat its rules, terminology, canonical grain, API contracts, and validation commands as the review rules.
2. Inspect the current relevant Git diff:
   - `git status --short`
   - `git diff --stat`
   - `git diff -- . ':(exclude)Phase_5/dist'`
   - Include relevant untracked files when reviewing them; do not treat an untracked file as invisible merely because it is absent from `git diff`.
3. Identify the changed application areas and run the standard relevant tests **before any AI/code review conclusions**.
4. Capture the exact test commands, exit status, pass/fail counts, and important failure output. If a test cannot run, state why.
5. Review the Git diff and repository code in addition to the tests. Tests are evidence, not a replacement for code review.
6. Produce the structured report below.

## Test selection

Use the changed files to select the narrowest standard suite that covers the change, then run all directly relevant suites:

- Spark or pipeline changes: `python -m pytest test_pipeline_91_92.py -v`
- API, router, service, schema, database, or API-facing changes: `python -m pytest Phase_4/tests/ -v`
- Frontend changes: from `Phase_5`, run `npm run build`
- Changes spanning multiple areas: run every applicable command above.
- If the diff changes only documentation, Claude command files, or tests, run the closest affected suite when one exists and explain the choice.

Never claim that tests passed unless the command actually completed successfully. Do not run destructive commands or alter data.

## Six review categories

For each category, report `PASS`, `FINDING`, or `NOT ASSESSABLE`, a severity (`NONE`, `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`), concrete evidence, and a recommendation. Distinguish confirmed issues from possible risks.

### 1. Data grain

Check whether the change can introduce duplicate rows at the canonical grain `(grid_id, timestamp)` after country-code aggregation. Inspect grouping keys, joins, unions, writes, and tests. Do not assume a test proves the absence of duplicates unless it actually checks the relevant path.

### 2. Feature leakage

Check whether any feature, baseline, label, aggregation, or lookup can use information after `feature_timestamp`. Inspect time filters, window boundaries, joins, and feature tests. Treat an unclear temporal boundary as a possible risk, not a confirmed issue.

### 3. Geographic join

Check every GeoJSON join key. The required key is `features[].properties.cellId` mapped to `grid_id`; flag use of the 0-based `featureid` field as a finding.

### 4. API contract

Check response models, JSON fields, status behavior, query semantics, and callers. Flag removals, renames, type changes, or incompatible behavior. Additive fields are normally compatible, but still identify missing test coverage.

### 5. Terminology

Check new code, API text, documentation, and UI text against `CLAUDE.md`. Flag assertions of confirmed congestion or descriptions of proportional activity measures as counts or MB. Keep observed elevated or high activity separate from unsupported operational conclusions.

### 6. Missing tests

List important tests that should exist for the changed behavior but are absent or insufficient. Do not call missing coverage a confirmed runtime bug unless the code evidence supports that conclusion.

## Report format

Return a concise Markdown report with this exact top-level structure:

```markdown
# Engineering Review

## Test Results
- Commands:
- Result:
- Failures or blocked checks:

## Changed Files Reviewed
- path: why it is relevant

## Findings
### Data grain
- Status: PASS | FINDING | NOT ASSESSABLE
- Severity: NONE | LOW | MEDIUM | HIGH | CRITICAL
- Evidence:
- Recommendation:

### Feature leakage
- Status:
- Severity:
- Evidence:
- Recommendation:

### Geographic join
- Status:
- Severity:
- Evidence:
- Recommendation:

### API contract
- Status:
- Severity:
- Evidence:
- Recommendation:

### Terminology
- Status:
- Severity:
- Evidence:
- Recommendation:

### Missing tests
- Status:
- Severity:
- Evidence:
- Recommendation:

## Recommended Additional Tests
- Test and reason

## Overall Risks and Uncertainties
- Confirmed issues:
- Possible risks:
- Test limitations:
- Human decision required:
```

Ground every statement in the current diff, repository code, project rules, or captured test output. Do not invent behavior, test results, or deployment status.

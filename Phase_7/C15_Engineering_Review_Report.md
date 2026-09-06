# C15 - Headless / CI Engineering Review

## Command Location

The reusable Claude Code slash command is stored at:

```text
.claude/commands/engineering-review.md
```

This is the project Claude Code commands location used by the existing NOPIS commands such as `/check-pipeline` and `/review-anomaly`.

## How to Run

After making a code change, run this command in Claude Code:

```text
/engineering-review
```

The command reviews the current working-tree change. It does not modify files or perform approval, merge, commit, push, deployment, or production operations.

## Command Workflow

1. Read `CLAUDE.md` first and apply its project rules.
2. Inspect `git status`, the diff summary, the relevant diff, and relevant untracked files.
3. Determine which standard tests cover the changed areas.
4. Run those tests before making review conclusions.
5. Capture commands, exit status, passes, failures, and blocked checks.
6. Review the code change separately from the tests.
7. Check data grain, feature leakage, geographic joins, API contracts, terminology, and missing tests.
8. Return an advisory Markdown engineering review with findings, severities, evidence, recommendations, and uncertainties.

Tests are never replaced by the AI review. A passing test suite does not automatically mean the change is risk-free.

## Tests It Runs

The command selects all directly relevant standard checks:

| Changed area | Command | Reason |
|---|---|---|
| Spark or pipeline | `python -m pytest test_pipeline_91_92.py -v` | Validates the repository's pipeline behavior and failure paths |
| API or database-facing code | `python -m pytest Phase_4/tests/ -v` | Validates API routes, services, schemas, and API contracts |
| Frontend | `Set-Location Phase_5; npm run build` | Validates the Vite production build |
| Multiple areas | All applicable commands | Prevents one affected layer from being skipped |

Documentation-only, command-only, or test-only changes are reported with the closest applicable validation, or explicitly marked as not requiring an application suite.

## Information Used by the Review

The review is grounded only in:

- `CLAUDE.md` and its project rules;
- the current Git status and relevant diff;
- relevant untracked changed files;
- repository source code and tests;
- actual test output and exit codes.

The command does not use unstated assumptions, invented test results, secrets, or external production data.

## Six Review Categories

Each category receives a status and severity:

- **Data grain:** duplicate risk at `(grid_id, timestamp)` after country-code aggregation.
- **Feature leakage:** information used after `feature_timestamp`.
- **Geographic join:** correct use of `properties.cellId`, never the 0-based `featureid`.
- **API contract:** breaking response shape, type, status, or query behavior.
- **Terminology:** prohibited claims about confirmed congestion or activity units described as counts or MB.
- **Missing tests:** important behavior not covered by existing tests.

Confirmed issues are separated from possible risks. Missing test coverage is not presented as a confirmed runtime defect without supporting code evidence.

## Review Report Format

The generated report contains:

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
- Status:
- Severity:
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

The report is advisory. Human reviewers retain all approval and deployment decisions.

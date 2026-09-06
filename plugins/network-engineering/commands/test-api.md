<!-- 299. Package them into a project or team plugin. -->
---
description: Run the automated API test suite and summarize passes, failures, and execution duration (Engineering-oriented)
---

# /test-api

Executes the Phase 4 pytest test suite, verifying all endpoints, contracts, and schema boundaries without manual test runner invocation.

## Usage
```text
/test-api [optional_test_path]
```

### Examples
```text
/test-api
/test-api Phase_4/tests/test_hotspots_alerts.py
```

## Behind the Scenes
Executes:
```bash
python Phase_7/c_tasks/project_commands.py test-api [optional_test_path]
```

## Expected Output
- **Overall Status**: `PASS` or `FAIL`
- **Command Executed**: Full pytest command string
- **Test Metrics**: Passed count, Failed count, Warning count, Duration in seconds
- **Failure Summary**: Clean list of failing test names and failure reasons (if any)

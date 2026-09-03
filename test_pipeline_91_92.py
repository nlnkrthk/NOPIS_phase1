# ================================================================
# DE2 / SP7 — Activity 91 + Activity 92 Test Script
#
# Tests:
# 91. Test the empty-input path (FileNotFoundError) and
#     the Spark-failure path (unexpected exception).
# 92. Confirm analytics files are produced only after
#     successful ingestion (no partial writes on failure).
# ================================================================

import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ── Make sure the NOPIS root is importable ──────────────────────
_ROOT = Path(__file__).resolve().parents[0]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from spark.ingestion import read_raw
from spark.writer import write_outputs

logging.basicConfig(level=logging.WARNING)


# ================================================================
# Shared fixtures
# ================================================================

@pytest.fixture()
def minimal_raw_csv(tmp_path):
    """Write a single valid raw CSV into tmp_path/raw/ and return its folder."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    csv_file = raw_dir / "sms-call-internet-mi-2013-11-01.csv"
    df = pd.DataFrame({
        "datetime":    ["2013-11-01 00:00:00", "2013-11-01 01:00:00"],
        "CellID":      [1, 2],
        "countrycode": [39, 39],
        "smsin":       [1.0, 2.0],
        "smsout":      [0.5, 1.5],
        "callin":      [3.0, 4.0],
        "callout":     [1.0, 2.0],
        "internet":    [10.0, 20.0],
    })
    df.to_csv(csv_file, index=False)
    return raw_dir


@pytest.fixture()
def output_dirs(tmp_path):
    """Return processed and analytics sub-directories (created on demand)."""
    processed  = tmp_path / "processed"
    analytics  = tmp_path / "analytics"
    return processed, analytics


# ================================================================
# 91. Test the empty-input path and the Spark-failure path.
# ================================================================

class TestEmptyInputPath:
    """91. Empty-input path: read_raw raises FileNotFoundError when raw/ is empty."""

    def test_empty_raw_directory_raises(self, tmp_path):
        # 91. empty-input path — no CSV files present → FileNotFoundError
        empty_raw = tmp_path / "raw"
        empty_raw.mkdir()

        mock_spark = MagicMock()

        with pytest.raises(FileNotFoundError) as exc_info:
            read_raw(mock_spark, str(empty_raw))

        assert "sms-call-internet-mi-*.csv" in str(exc_info.value)
        assert str(empty_raw) in str(exc_info.value)

    def test_nonexistent_raw_directory_raises(self, tmp_path):
        # 91. empty-input path — directory does not exist → FileNotFoundError
        nonexistent = tmp_path / "does_not_exist"
        mock_spark = MagicMock()

        with pytest.raises(FileNotFoundError):
            read_raw(mock_spark, str(nonexistent))

    def test_wrong_pattern_files_ignored(self, tmp_path):
        # 91. empty-input path — files present but wrong name pattern → FileNotFoundError
        wrong_dir = tmp_path / "raw"
        wrong_dir.mkdir()
        (wrong_dir / "some-other-data.csv").write_text("a,b\n1,2")

        mock_spark = MagicMock()

        with pytest.raises(FileNotFoundError):
            read_raw(mock_spark, str(wrong_dir))


class TestSparkFailurePath:
    """91. Spark-failure path: pipeline catches exceptions and does NOT write outputs."""

    def _make_paths(self, tmp_path):
        processed = tmp_path / "processed"
        analytics = tmp_path / "analytics"
        return processed, analytics

    def test_spark_session_creation_failure_no_outputs(self, tmp_path, minimal_raw_csv):
        # 91. Spark-failure path — SparkSession creation crashes → no analytics files written
        processed, analytics = self._make_paths(tmp_path)

        with (
            patch("spark.telecom_pipeline.process_landing", return_value={"detected": 0, "valid": 0, "rejected": 0}),
            patch("spark.telecom_pipeline.create_spark_session", side_effect=RuntimeError("Spark init failed")),
            patch("sys.exit"),
        ):
            from spark.telecom_pipeline import main
            import argparse

            with patch("spark.telecom_pipeline._parse_args") as mock_args:
                mock_args.return_value = argparse.Namespace(
                    landing=str(tmp_path / "landing"),
                    raw=str(minimal_raw_csv),
                    rejected=str(tmp_path / "rejected"),
                    logs=str(tmp_path / "logs"),
                    processed=str(processed),
                    analytics=str(analytics),
                    reference=str(tmp_path / "ref.geojson"),
                    input=None,
                    config=None,
                )
                main()

        # Analytics folder must NOT exist — nothing was written on Spark failure
        assert not (analytics / "hourly_grid_summary").exists(), (
            "hourly_grid_summary should NOT be created when Spark fails"
        )
        assert not (analytics / "summary_csv").exists(), (
            "summary_csv should NOT be created when Spark fails"
        )

    def test_read_raw_failure_no_outputs(self, tmp_path):
        # 91. Spark-failure path — read_raw raises FileNotFoundError → sys.exit(1), no outputs
        processed, analytics = self._make_paths(tmp_path)
        empty_raw = tmp_path / "raw"
        empty_raw.mkdir()

        with (
            patch("spark.telecom_pipeline.process_landing", return_value={"detected": 0, "valid": 0, "rejected": 0}),
            patch("spark.telecom_pipeline.create_spark_session", return_value=MagicMock()),
            patch("sys.exit") as mock_exit,
        ):
            from spark.telecom_pipeline import main
            import argparse

            with patch("spark.telecom_pipeline._parse_args") as mock_args:
                mock_args.return_value = argparse.Namespace(
                    landing=str(tmp_path / "landing"),
                    raw=str(empty_raw),
                    rejected=str(tmp_path / "rejected"),
                    logs=str(tmp_path / "logs"),
                    processed=str(processed),
                    analytics=str(analytics),
                    reference=str(tmp_path / "ref.geojson"),
                    input=None,
                    config=None,
                )
                main()

        # sys.exit(1) must have been called
        mock_exit.assert_called_once_with(1)

        # No output files written
        assert not (analytics / "hourly_grid_summary").exists()
        assert not (processed / "enriched_hourly_grid").exists()

    def test_unexpected_exception_no_outputs(self, tmp_path, minimal_raw_csv):
        # 91. Spark-failure path — aggregate() raises unexpected exception → sys.exit(1), no outputs
        processed, analytics = self._make_paths(tmp_path)

        mock_df = MagicMock()
        mock_spark = MagicMock()

        with (
            patch("spark.telecom_pipeline.process_landing", return_value={"detected": 1, "valid": 1, "rejected": 0}),
            patch("spark.telecom_pipeline.create_spark_session", return_value=mock_spark),
            patch("spark.telecom_pipeline.read_raw", return_value=mock_df),
            patch("spark.telecom_pipeline.clean", return_value=(mock_df, 0, {})),
            patch("spark.telecom_pipeline.aggregate", side_effect=ValueError("Grain duplicate detected")),
            patch("sys.exit") as mock_exit,
        ):
            from spark.telecom_pipeline import main
            import argparse

            with patch("spark.telecom_pipeline._parse_args") as mock_args:
                mock_args.return_value = argparse.Namespace(
                    landing=str(tmp_path / "landing"),
                    raw=str(minimal_raw_csv),
                    rejected=str(tmp_path / "rejected"),
                    logs=str(tmp_path / "logs"),
                    processed=str(processed),
                    analytics=str(analytics),
                    reference=str(tmp_path / "ref.geojson"),
                    input=None,
                    config=None,
                )
                main()

        mock_exit.assert_called_once_with(1)
        assert not (analytics / "hourly_grid_summary").exists()
        assert not (processed / "enriched_hourly_grid").exists()


# ================================================================
# 92. Confirm analytics files are produced only after successful ingestion.
# ================================================================

class TestAnalyticsOnlyAfterSuccess:
    """92. Analytics files exist iff the full pipeline succeeds."""

    def test_analytics_files_present_on_success(self, tmp_path, minimal_raw_csv):
        # 92. Success path — write_outputs is called once and creates analytics folder
        processed = tmp_path / "processed"
        analytics = tmp_path / "analytics"
        mock_df = MagicMock()
        mock_spark = MagicMock()

        written = []

        def fake_write_outputs(enriched_df, processed_path, analytics_path):
            # Simulate successful write by touching expected output directories
            (Path(analytics_path) / "hourly_grid_summary").mkdir(parents=True, exist_ok=True)
            (Path(analytics_path) / "summary_csv").mkdir(parents=True, exist_ok=True)
            (Path(processed_path) / "enriched_hourly_grid").mkdir(parents=True, exist_ok=True)
            written.append(True)
            return 2

        with (
            patch("spark.telecom_pipeline.process_landing", return_value={"detected": 1, "valid": 1, "rejected": 0}),
            patch("spark.telecom_pipeline.create_spark_session", return_value=mock_spark),
            patch("spark.telecom_pipeline.read_raw", return_value=mock_df),
            patch("spark.telecom_pipeline.clean", return_value=(mock_df, 0, {})),
            patch("spark.telecom_pipeline.aggregate", return_value=mock_df),
            patch("spark.telecom_pipeline.enrich", return_value=mock_df),
            patch("spark.telecom_pipeline.write_outputs", side_effect=fake_write_outputs),
            patch("spark.telecom_pipeline.load_warehouse"),
            patch("sys.exit"),
        ):
            from spark.telecom_pipeline import main
            import argparse

            with patch("spark.telecom_pipeline._parse_args") as mock_args:
                mock_args.return_value = argparse.Namespace(
                    landing=str(tmp_path / "landing"),
                    raw=str(minimal_raw_csv),
                    rejected=str(tmp_path / "rejected"),
                    logs=str(tmp_path / "logs"),
                    processed=str(processed),
                    analytics=str(analytics),
                    reference=str(tmp_path / "ref.geojson"),
                    input=None,
                    config=None,
                )
                main()

        # 92. analytics files exist after success
        assert (analytics / "hourly_grid_summary").exists(), "hourly_grid_summary must exist after SUCCESS"
        assert (analytics / "summary_csv").exists(), "summary_csv must exist after SUCCESS"
        assert (processed / "enriched_hourly_grid").exists(), "enriched_hourly_grid must exist after SUCCESS"
        assert written, "write_outputs must have been called"

    def test_analytics_files_absent_on_pipeline_failure(self, tmp_path, minimal_raw_csv):
        # 92. Failure path — enrichment crashes → write_outputs never called → no analytics files
        processed = tmp_path / "processed"
        analytics = tmp_path / "analytics"
        mock_df = MagicMock()
        mock_spark = MagicMock()

        with (
            patch("spark.telecom_pipeline.process_landing", return_value={"detected": 1, "valid": 1, "rejected": 0}),
            patch("spark.telecom_pipeline.create_spark_session", return_value=mock_spark),
            patch("spark.telecom_pipeline.read_raw", return_value=mock_df),
            patch("spark.telecom_pipeline.clean", return_value=(mock_df, 0, {})),
            patch("spark.telecom_pipeline.aggregate", return_value=mock_df),
            patch("spark.telecom_pipeline.enrich", side_effect=RuntimeError("GeoJSON join exploded")),
            patch("sys.exit"),
        ):
            from spark.telecom_pipeline import main
            import argparse

            with patch("spark.telecom_pipeline._parse_args") as mock_args:
                mock_args.return_value = argparse.Namespace(
                    landing=str(tmp_path / "landing"),
                    raw=str(minimal_raw_csv),
                    rejected=str(tmp_path / "rejected"),
                    logs=str(tmp_path / "logs"),
                    processed=str(processed),
                    analytics=str(analytics),
                    reference=str(tmp_path / "ref.geojson"),
                    input=None,
                    config=None,
                )
                main()

        # 92. analytics folder must not contain outputs when pipeline failed
        assert not (analytics / "hourly_grid_summary").exists(), (
            "hourly_grid_summary must NOT exist after pipeline failure"
        )
        assert not (analytics / "summary_csv").exists(), (
            "summary_csv must NOT exist after pipeline failure"
        )
        assert not (processed / "enriched_hourly_grid").exists(), (
            "enriched_hourly_grid must NOT exist after pipeline failure"
        )

    def test_write_outputs_not_called_on_failure(self, tmp_path, minimal_raw_csv):
        # 92. Confirm write_outputs is never invoked when any upstream stage fails
        mock_df = MagicMock()
        mock_spark = MagicMock()
        write_calls = []

        def spy_write(enriched_df, processed_path, analytics_path):
            write_calls.append(True)

        with (
            patch("spark.telecom_pipeline.process_landing", return_value={"detected": 1, "valid": 1, "rejected": 0}),
            patch("spark.telecom_pipeline.create_spark_session", return_value=mock_spark),
            patch("spark.telecom_pipeline.read_raw", return_value=mock_df),
            patch("spark.telecom_pipeline.clean", side_effect=RuntimeError("Cleaning blew up")),
            patch("spark.telecom_pipeline.write_outputs", side_effect=spy_write),
            patch("sys.exit"),
        ):
            from spark.telecom_pipeline import main
            import argparse

            with patch("spark.telecom_pipeline._parse_args") as mock_args:
                mock_args.return_value = argparse.Namespace(
                    landing=str(tmp_path / "landing"),
                    raw=str(minimal_raw_csv),
                    rejected=str(tmp_path / "rejected"),
                    logs=str(tmp_path / "logs"),
                    processed=str(tmp_path / "processed"),
                    analytics=str(tmp_path / "analytics"),
                    reference=str(tmp_path / "ref.geojson"),
                    input=None,
                    config=None,
                )
                main()

        assert not write_calls, "write_outputs must NOT be called when an upstream stage fails"


# ================================================================
# Quick smoke run
# ================================================================

if __name__ == "__main__":
    import subprocess
    subprocess.run([sys.executable, "-m", "pytest", __file__, "-v"], check=False)

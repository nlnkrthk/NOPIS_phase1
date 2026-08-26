import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from usage_processor import UsageProcessor

def test_load_data():
    processor = UsageProcessor(
        "../../data/sms-call-internet-mi-2013-11-01.csv"
    )

    data = processor.load_data()

    assert isinstance(data, pd.DataFrame)
    assert len(data) > 0

def test_clean_data():
    data = pd.DataFrame({
        "datetime": ["2013-11-01 00:00:00"],
        "CellID": [1],
        "countrycode": [0],
        "smsin": [1.0],
        "smsout": [1.0],
        "callin": [1.0],
        "callout": [1.0],
        "internet": [1.0]
    })

    processor = UsageProcessor(data)

    processor.load_data()
    cleaned = processor.clean_data()

    assert len(cleaned) == 1


def test_derive_time_features():
    data = pd.DataFrame({
        "datetime": ["2013-11-01 13:00:00"],
        "CellID": [1],
        "countrycode": [0],
        "smsin": [1.0],
        "smsout": [1.0],
        "callin": [1.0],
        "callout": [1.0],
        "internet": [1.0]
    })

    processor = UsageProcessor(data)

    processor.load_data()
    processor.clean_data()
    result = processor.derive_time_features()

    assert "date" in result.columns
    assert "hour" in result.columns
    assert "day_of_week" in result.columns


def test_aggregate_to_grid_time():
    data = pd.DataFrame({
        "datetime": [
            "2013-11-01 00:00:00",
            "2013-11-01 00:00:00"
        ],
        "CellID": [1, 1],
        "countrycode": [0, 33],
        "smsin": [1.0, 2.0],
        "smsout": [1.0, 2.0],
        "callin": [1.0, 2.0],
        "callout": [1.0, 2.0],
        "internet": [1.0, 2.0]
    })

    processor = UsageProcessor(data)

    processor.load_data()
    processor.clean_data()
    processor.derive_time_features()

    result = processor.aggregate_to_grid_time()

    assert len(result) == 1
    assert not result.duplicated(
        subset=["datetime", "CellID"]
    ).any()
    assert "countrycode" not in result.columns


def test_derive_activity_features():
    data = pd.DataFrame({
        "datetime": ["2013-11-01 00:00:00"],
        "CellID": [1],
        "smsin": [1.0],
        "smsout": [2.0],
        "callin": [3.0],
        "callout": [4.0],
        "internet": [5.0],
        "date": ["2013-11-01"],
        "hour": [0],
        "day_of_week": ["Friday"]
    })

    processor = UsageProcessor(data)

    processor.df = data

    result = processor.derive_activity_features()

    assert "total_sms" in result.columns
    assert "total_calls" in result.columns
    assert "total_activity" in result.columns

def test_compute_kpis():
    data = pd.DataFrame({
        "datetime": ["2013-11-01 00:00:00"],
        "date": ["2013-11-01"],
        "hour": [0],
        "day_of_week": ["Friday"],
        "CellID": [1],
        "total_sms": [3.0],
        "total_calls": [7.0],
        "total_activity": [15.0]
    })

    processor = UsageProcessor(data)
    processor.df = data

    kpis = processor.compute_kpis()

    assert isinstance(kpis, dict)
    assert "total_activity" in kpis
    assert "busiest_hour" in kpis
    assert "busiest_grid" in kpis

def test_export_summary(tmp_path):
    data = pd.DataFrame({
        "datetime": ["2013-11-01 00:00:00"],
        "date": ["2013-11-01"],
        "hour": [0],
        "day_of_week": ["Friday"],
        "CellID": [1],
        "total_sms": [3.0],
        "total_calls": [7.0],
        "total_activity": [15.0]
    })

    processor = UsageProcessor(data)
    processor.df = data

    processor.export_summary(tmp_path)

    assert (tmp_path / "daily_summary.csv").exists()
    assert (tmp_path / "grid_summary.csv").exists()


# 6. Write one small unit-style validation for each major method.

def test_full_processing_pipeline(tmp_path):
    processor = UsageProcessor(
        "../../data/sms-call-internet-mi-2013-11-01.csv"
    )

    # 1. load_data()
    loaded = processor.load_data()
    assert isinstance(loaded, pd.DataFrame)

    # 2. clean_data()
    cleaned = processor.clean_data()
    assert cleaned is not None

    # 3. derive_time_features()
    timed = processor.derive_time_features()
    assert "hour" in timed.columns

    # 4. aggregate_to_grid_time()
    aggregated = processor.aggregate_to_grid_time()
    assert not aggregated.duplicated(
        subset=["datetime", "CellID"]
    ).any()

    # 5. derive_activity_features()
    features = processor.derive_activity_features()
    assert "total_activity" in features.columns

    # 6. compute_kpis()
    kpis = processor.compute_kpis()
    assert isinstance(kpis, dict)

    # 7. export_summary()
    daily_summary, grid_summary = processor.export_summary(tmp_path)

    assert len(daily_summary) > 0
    assert len(grid_summary) > 0
    assert (tmp_path / "daily_summary.csv").exists()
    assert (tmp_path / "grid_summary.csv").exists()
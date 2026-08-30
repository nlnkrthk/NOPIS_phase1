"""
Landing-to-Raw ingestion module for DE2.

Flow:
    data/landing/
        ↓
    detect_files()
        ↓
    validate_schema()
        ↓
    validate_minimum_quality()
        ↓
    route_file()
        ↓
    data/raw/ OR data/rejected/
"""

import logging
import shutil
from pathlib import Path

import pandas as pd


logger = logging.getLogger(__name__)


# ================================================================
# DE2 configuration
# ================================================================

CSV_GLOB_PATTERN = "sms-call-internet-mi-*.csv"

REQUIRED_COLUMNS = [
    "datetime",
    "CellID",
    "countrycode",
    "smsin",
    "smsout",
    "callin",
    "callout",
    "internet",
]

ACTIVITY_COLUMNS = [
    "smsin",
    "smsout",
    "callin",
    "callout",
    "internet",
]


# ================================================================
# 83. Implement detect_files(), validate_schema(),
# validate_minimum_quality() and route_file() for the daily
# activity CSVs. Detect using the pattern sms-call-internet-mi-*.csv.
# Do not treat the GeoJSON reference as a daily ingest candidate.
# ================================================================


def detect_files(landing_path):
    """
    Detect daily telecom CSV files in the landing zone.

    Only files matching:
        sms-call-internet-mi-*.csv

    are considered ingestion candidates.

    The GeoJSON reference file is not detected because
    it does not match the CSV pattern.
    """

    landing_folder = Path(landing_path)

    if not landing_folder.exists():
        logger.warning(
            "Landing folder does not exist: %s",
            landing_folder
        )
        return []

    files = sorted(
        file
        for file in landing_folder.glob(CSV_GLOB_PATTERN)
        if file.is_file()
    )

    logger.info(
        "Detected %d daily CSV file(s) in %s",
        len(files),
        landing_folder
    )

    for file in files:
        logger.info(
            "Detected file: %s",
            file.name
        )

    return files


def validate_schema(file_path):
    """
    Validate that the CSV contains all required columns.

    Returns:
        (True, "Schema validation passed")
        or
        (False, "specific failure reason")
    """

    file_path = Path(file_path)

    try:
        # Read only the header because we only need
        # the column names for schema validation.
        df = pd.read_csv(
            file_path,
            nrows=0
        )

    except Exception as exc:
        reason = f"Unable to read CSV: {exc}"

        logger.error(
            "%s | %s",
            file_path.name,
            reason
        )

        return False, reason

    actual_columns = list(df.columns)

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in actual_columns
    ]

    if missing_columns:

        reason = (
            "Missing required column(s): "
            + ", ".join(missing_columns)
        )

        logger.warning(
            "%s | %s",
            file_path.name,
            reason
        )

        return False, reason

    logger.info(
        "%s | Schema validation passed",
        file_path.name
    )

    return True, "Schema validation passed"


def validate_minimum_quality(file_path):
    """
    Perform minimum data-quality validation.

    Checks:
        1. File is not empty.
        2. datetime values that are present are valid.
        3. Activity values that are present are numeric.
        4. Activity values that are present are not negative.

    Missing activity values are allowed because they occur
    naturally in the source telecom dataset.

    Returns:
        (True, "Minimum quality validation passed")
        or
        (False, "specific failure reason")
    """

    file_path = Path(file_path)

    try:
        df = pd.read_csv(file_path)

    except Exception as exc:
        reason = f"Unable to read CSV: {exc}"

        logger.error(
            "%s | %s",
            file_path.name,
            reason
        )

        return False, reason

    # ------------------------------------------------------------
    # Check 1 — File must contain rows
    # ------------------------------------------------------------

    if df.empty:

        reason = "File contains zero rows"

        logger.warning(
            "%s | %s",
            file_path.name,
            reason
        )

        return False, reason

    # ------------------------------------------------------------
    # Check 2 — Validate datetime
    # ------------------------------------------------------------

    parsed_datetime = pd.to_datetime(
        df["datetime"],
        errors="coerce"
    )

    # Missing datetime values are considered invalid.
    invalid_datetime_count = parsed_datetime.isna().sum()

    if invalid_datetime_count > 0:

        reason = (
            f"Malformed or missing datetime value(s): "
            f"{invalid_datetime_count}"
        )

        logger.warning(
            "%s | %s",
            file_path.name,
            reason
        )

        return False, reason

    # ------------------------------------------------------------
    # Check 3 and 4 — Validate activity columns
    # ------------------------------------------------------------

    for column in ACTIVITY_COLUMNS:

        # IMPORTANT:
        # The source dataset naturally contains missing values.
        # Missing activity values are allowed.
        non_null_values = df[column].dropna()

        # Convert only the values that actually exist.
        numeric_values = pd.to_numeric(
            non_null_values,
            errors="coerce"
        )

        # If a non-null value cannot be converted to a number,
        # the file is invalid.
        invalid_numeric_count = numeric_values.isna().sum()

        if invalid_numeric_count > 0:

            reason = (
                f"Invalid numeric value(s) in {column}: "
                f"{invalid_numeric_count}"
            )

            logger.warning(
                "%s | %s",
                file_path.name,
                reason
            )

            return False, reason

        # Negative activity values are not allowed.
        negative_count = (
            numeric_values < 0
        ).sum()

        if negative_count > 0:

            reason = (
                f"Negative activity value(s) in {column}: "
                f"{negative_count}"
            )

            logger.warning(
                "%s | %s",
                file_path.name,
                reason
            )

            return False, reason

    logger.info(
        "%s | Minimum quality validation passed",
        file_path.name
    )

    return True, "Minimum quality validation passed"


def route_file(
    file_path,
    raw_path,
    rejected_path,
    status,
    reason
):
    """
    Route a validated file to raw/ or rejected/.

    Valid files:
        data/raw/

    Invalid files:
        data/rejected/
    """

    file_path = Path(file_path)
    raw_folder = Path(raw_path)
    rejected_folder = Path(rejected_path)

    # ------------------------------------------------------------
    # Determine destination
    # ------------------------------------------------------------

    if status == "VALID":

        destination_folder = raw_folder

    else:

        destination_folder = rejected_folder

    destination_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    destination = destination_folder / file_path.name

    # ------------------------------------------------------------
    # Prevent accidental overwrite
    # ------------------------------------------------------------

    if destination.exists():

        logger.warning(
            "Destination already exists: %s",
            destination
        )

        return destination

    # ------------------------------------------------------------
    # Move file
    # ------------------------------------------------------------

    shutil.move(
        str(file_path),
        str(destination)
    )

    logger.info(
        "Routed %s → %s | status=%s | reason=%s",
        file_path.name,
        destination,
        status,
        reason
    )

    return destination

# 84. Write ingestion metadata for every file seen:
#     filename, status, row_count, reason, processed_at.

def write_ingestion_metadata(
    filename,
    status,
    row_count,
    reason,
    logs_path
):
    """
    Write an audit record for an ingestion file.

    Required metadata:
        filename
        status
        row_count
        reason
        processed_at
    """

    logs_folder = Path(logs_path)

    # Create logs/ if it does not exist.
    logs_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    log_file = logs_folder / "ingestion_log.csv"

    processed_at = pd.Timestamp.now().isoformat()

    metadata = pd.DataFrame([
        {
            "filename": filename,
            "status": status,
            "row_count": row_count,
            "reason": reason,
            "processed_at": processed_at,
        }
    ])

    # Append to the existing log.
    # Create the file with headers if it doesn't exist.
    metadata.to_csv(
        log_file,
        mode="a",
        header=not log_file.exists(),
        index=False
    )

    logger.info(
        "Ingestion metadata recorded: %s | %s | %s",
        filename,
        status,
        reason
    )


# ================================================================
# Orchestrator: Landing Ingestion Workflow
# ================================================================

def process_landing(
    landing_path,
    raw_path,
    rejected_path,
    logs_path,
):
    """
    Execute landing-to-raw ingestion workflow.

    1. Detect files in landing zone matching sms-call-internet-mi-*.csv.
    2. For each file:
       a. Check read integrity and get row count.
       b. Validate schema (required columns).
       c. Validate minimum data quality.
       d. Route to raw/ (if VALID) or rejected/ (if INVALID).
       e. Log audit metadata to logs_path/ingestion_log.csv.

    Parameters
    ----------
    landing_path : str or Path
        Directory where incoming files land.
    raw_path : str or Path
        Directory for validated raw files.
    rejected_path : str or Path
        Directory for quarantined/rejected files.
    logs_path : str or Path
        Directory for ingestion audit logs.

    Returns
    -------
    dict
        Summary with keys:
        - "detected": int (number of candidate files found)
        - "valid": int (number of files routed to raw)
        - "rejected": int (number of files routed to rejected)
        - "details": list of dicts with file status and reason
    """
    landing_path = Path(landing_path)
    raw_path = Path(raw_path)
    rejected_path = Path(rejected_path)
    logs_path = Path(logs_path)

    files = detect_files(landing_path)

    valid_count = 0
    rejected_count = 0
    details = []

    for file in files:
        logger.info("Processing landing file: %s", file.name)

        # --------------------------------------------------------
        # 1. Read row count / check file readability
        # --------------------------------------------------------
        try:
            df = pd.read_csv(file)
            row_count = len(df)
        except Exception as exc:
            row_count = 0
            reason = f"Unable to read CSV: {exc}"
            logger.error("%s | %s", file.name, reason)

            route_file(
                file,
                raw_path,
                rejected_path,
                "INVALID",
                reason,
            )
            write_ingestion_metadata(
                filename=file.name,
                status="INVALID",
                row_count=row_count,
                reason=reason,
                logs_path=logs_path,
            )
            rejected_count += 1
            details.append({
                "filename": file.name,
                "status": "INVALID",
                "row_count": row_count,
                "reason": reason,
            })
            continue

        # --------------------------------------------------------
        # 2. Validate schema
        # --------------------------------------------------------
        schema_valid, schema_reason = validate_schema(file)
        if not schema_valid:
            route_file(
                file,
                raw_path,
                rejected_path,
                "INVALID",
                schema_reason,
            )
            write_ingestion_metadata(
                filename=file.name,
                status="INVALID",
                row_count=row_count,
                reason=schema_reason,
                logs_path=logs_path,
            )
            rejected_count += 1
            details.append({
                "filename": file.name,
                "status": "INVALID",
                "row_count": row_count,
                "reason": schema_reason,
            })
            continue

        # --------------------------------------------------------
        # 3. Validate minimum quality
        # --------------------------------------------------------
        quality_valid, quality_reason = validate_minimum_quality(file)
        if not quality_valid:
            route_file(
                file,
                raw_path,
                rejected_path,
                "INVALID",
                quality_reason,
            )
            write_ingestion_metadata(
                filename=file.name,
                status="INVALID",
                row_count=row_count,
                reason=quality_reason,
                logs_path=logs_path,
            )
            rejected_count += 1
            details.append({
                "filename": file.name,
                "status": "INVALID",
                "row_count": row_count,
                "reason": quality_reason,
            })
            continue

        # --------------------------------------------------------
        # 4. File passed all validation -> Route to raw
        # --------------------------------------------------------
        route_file(
            file,
            raw_path,
            rejected_path,
            "VALID",
            "All validation checks passed",
        )
        write_ingestion_metadata(
            filename=file.name,
            status="VALID",
            row_count=row_count,
            reason="All validation checks passed",
            logs_path=logs_path,
        )
        valid_count += 1
        details.append({
            "filename": file.name,
            "status": "VALID",
            "row_count": row_count,
            "reason": "All validation checks passed",
        })

    summary = {
        "detected": len(files),
        "valid": valid_count,
        "rejected": rejected_count,
        "details": details,
    }

    logger.info(
        "Landing ingestion complete — Detected: %d, Valid: %d, Rejected: %d",
        summary["detected"],
        summary["valid"],
        summary["rejected"],
    )

    return summary
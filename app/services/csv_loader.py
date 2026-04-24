from pathlib import Path
import os

import pandas as pd

from app.config import BASE_DIR
from app.db import replace_records
from app.services.aggregation_service import invalidate_analysis_cache
from app.services.report_service import invalidate_report_cache
from app.utils.normalization import normalize_dataframe


def _normalize_directory_input(directory_path: str) -> Path:
    raw = (directory_path or "").strip().strip('"').strip("'")
    if not raw:
        raise ValueError("CSV directory path is empty.")

    directory = Path(raw).expanduser()
    if not directory.is_absolute():
        directory = BASE_DIR / directory
    return directory.resolve()


def _csv_files_in_directory(directory: Path) -> list[Path]:
    # Accept .csv files case-insensitively and support nested folders because
    # desktop export directories are often structured by subfolder.
    return sorted(path for path in directory.rglob("*") if path.is_file() and path.suffix.lower() == ".csv")


def import_csv_directory(connection, directory_path: str) -> dict:
    # Relative paths are resolved from backend/, so API calls can use
    # "data/sample_csvs" independent of the current shell directory.
    directory = _normalize_directory_input(directory_path)
    if not directory.exists() or not directory.is_dir():
        raise ValueError(f"CSV directory does not exist: {directory}")
    if not os.access(directory, os.R_OK):
        raise ValueError(f"CSV directory is not readable: {directory}")

    csv_files = _csv_files_in_directory(directory)
    if not csv_files:
        raise ValueError(f"No CSV files found in: {directory}")

    frames = []
    file_results = []
    for csv_file in csv_files:
        # dtype=str preserves leading zeros in zipcodes and unit numbers.
        # Numeric conversion happens later in normalization.py.
        try:
            frame = pd.read_csv(csv_file, dtype=str)
        except PermissionError as exc:
            raise ValueError(f"CSV file is not readable: {csv_file}") from exc
        except OSError as exc:
            raise ValueError(f"CSV file could not be opened: {csv_file} ({exc})") from exc
        normalized, metadata = normalize_dataframe(frame, csv_file.name)
        frames.append(normalized)
        file_results.append(metadata)

    combined = pd.concat(frames, ignore_index=True)
    records = combined.to_dict(orient="records")
    # For the demo importer one successful call replaces the active dataset.
    inserted = replace_records(connection, records)
    invalidate_analysis_cache()
    invalidate_report_cache()

    return {
        "imported_files": len(csv_files),
        "inserted_rows": inserted,
        "files": file_results,
        "notes": [
            "CSV columns are normalized case-insensitively.",
            "Known aliases such as street_name, house_number, energyusage [kWh], livingspace [m²], emission factor [g/kWh] and postal_code are mapped to the internal schema.",
            "If full_address is present, street and housenumber are derived from it.",
            "building and unitnumber are kept out of the fachliche IDs; buildings use city + street + house_number, apartments use apartment_number.",
            "Rows with invalid dates, negative energy usage or missing required numeric values are skipped.",
        ],
    }


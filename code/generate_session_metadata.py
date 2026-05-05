#!/usr/bin/env python3
"""Build a per-session metadata CSV from AIND JSON files."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


DATA_DIR = Path("/root/capsule/data")
OUTPUT_CSV = Path("/root/capsule/results/tables/session_metadata.csv")
LIST_SEPARATOR = "; "
LIST_COLUMNS = ["modality_abbreviations", "tags", "investigators"]

FIELDNAMES = [
    "subject_id",
    "date",
    "duration",
    "type",
    "modality_abbreviations",
    "tags",
    "name",
    "project_name",
    "investigators",
    "nwb_path",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a CSV summarizing session metadata from AIND JSON files."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DATA_DIR,
        help=f"Directory containing one subdirectory per session. Default: {DATA_DIR}",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_CSV,
        help=f"CSV output path. Default: {OUTPUT_CSV}",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def parse_datetime(value: str | None, *, keep_timezone: bool) -> datetime | None:
    if not value:
        return None

    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if keep_timezone:
        return parsed
    return parsed.replace(tzinfo=None)


def duration_seconds(start_time: str | None, end_time: str | None) -> str:
    start = parse_datetime(start_time, keep_timezone=True)
    end = parse_datetime(end_time, keep_timezone=True)

    if start is None or end is None:
        return ""

    seconds = (end - start).total_seconds()

    # Some acquisition files mark the end time as "Z" even though the clock time
    # matches the local epoch timestamps. Fall back to wall-clock subtraction.
    if seconds < 0:
        wall_start = parse_datetime(start_time, keep_timezone=False)
        wall_end = parse_datetime(end_time, keep_timezone=False)
        if wall_start is not None and wall_end is not None:
            seconds = (wall_end - wall_start).total_seconds()

    return f"{seconds:.3f}"


def date_from_start_time(start_time: str | None) -> str:
    parsed = parse_datetime(start_time, keep_timezone=False)
    if parsed is None:
        return ""
    return parsed.date().isoformat()


def join_values(values: Any) -> str:
    if values is None:
        return ""
    if isinstance(values, list):
        return LIST_SEPARATOR.join(str(value) for value in values if value is not None)
    return str(values)


def modality_abbreviations(data_description: dict[str, Any]) -> str:
    abbreviations: list[str] = []
    for modality in data_description.get("modalities") or []:
        if not isinstance(modality, dict):
            continue
        abbreviation = modality.get("abbreviation")
        if abbreviation and abbreviation not in abbreviations:
            abbreviations.append(str(abbreviation))
    return LIST_SEPARATOR.join(abbreviations)


def investigator_names(data_description: dict[str, Any]) -> str:
    names: list[str] = []
    for investigator in data_description.get("investigators") or []:
        if isinstance(investigator, dict):
            name = investigator.get("name")
        else:
            name = investigator
        if name:
            names.append(str(name))
    return LIST_SEPARATOR.join(names)


def find_nwb_path(session_dir: Path) -> str:
    patterns = ("*.nwb", "*.nwb.zarr", "*.nwb.hdf5", "*.nwb.h5")
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(session_dir.glob(pattern))

    if not matches:
        return ""
    return str(sorted(matches)[0])


def session_row(session_dir: Path) -> dict[str, str]:
    acquisition_path = session_dir / "acquisition.json"
    description_path = session_dir / "data_description.json"

    acquisition = load_json(acquisition_path)
    data_description = load_json(description_path)

    start_time = acquisition.get("acquisition_start_time")
    end_time = acquisition.get("acquisition_end_time")

    return {
        "subject_id": str(acquisition.get("subject_id") or data_description.get("subject_id") or ""),
        "date": date_from_start_time(start_time),
        "duration": duration_seconds(start_time, end_time),
        "type": str(acquisition.get("acquisition_type") or ""),
        "modality_abbreviations": modality_abbreviations(data_description),
        "tags": join_values(data_description.get("tags")),
        "name": str(data_description.get("name") or ""),
        "project_name": str(data_description.get("project_name") or ""),
        "investigators": investigator_names(data_description),
        "nwb_path": find_nwb_path(session_dir),
    }


def session_dirs(data_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in data_dir.iterdir()
        if path.is_dir()
        and (path / "acquisition.json").exists()
        and (path / "data_description.json").exists()
    )


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def split_list_cell(value: Any) -> list[str]:
    if pd.isna(value) or value == "":
        return []
    return [item.strip() for item in str(value).split(LIST_SEPARATOR) if item.strip()]


def load_csv_for_display(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    for column in LIST_COLUMNS:
        df[column] = df[column].apply(split_list_cell)
    return df


def main() -> None:
    args = parse_args()
    rows = [session_row(path) for path in session_dirs(args.data_dir)]
    write_csv(rows, args.output)
    print(f"Wrote {len(rows)} rows to {args.output}")

    df = load_csv_for_display(args.output)
    print("\nLoaded CSV with pandas; list-like columns restored from semicolon-separated cells:")
    with pd.option_context("display.max_columns", None, "display.max_colwidth", None, "display.width", 0):
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()

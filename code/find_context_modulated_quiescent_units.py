#!/usr/bin/env python3
"""Find units with large context modulation of quiescent firing rate."""

from __future__ import annotations

import argparse
import pathlib
from collections.abc import Iterable

import polars as pl
import polars_vec_ops  # noqa: F401 - registers .vec.join_between

import nwb_access


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "results" / "context_modulated_quiescent_units.csv"
DEFAULT_SUMMARY_OUTPUT = (
    REPO_ROOT / "results" / "context_modulated_quiescent_units_summary.csv"
)

SENSORY_CORTICAL_PREFIXES = ("AUD", "VIS", "SSp", "SSs", "GU")
UNIT_METADATA_COLUMNS = (
    "unit_id",
    "structure",
    "location",
    "firing_rate",
    "activity_drift",
    "is_not_drift",
    "is_qc_pass",
    "_nwb_path",
    "_table_index",
)
UNIT_SPIKE_COLUMNS = (*UNIT_METADATA_COLUMNS, "spike_times")
TRIAL_COLUMNS = (
    "trial_index",
    "block_index",
    "rewarded_modality",
    "quiescent_start_time",
    "quiescent_stop_time",
    "is_opto",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Scan available Dynamic Routing NWBs for units whose quiescent-period "
            "firing rate differs by context."
        )
    )
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV path for matching units. Default: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--summary-output",
        type=pathlib.Path,
        default=DEFAULT_SUMMARY_OUTPUT,
        help=f"CSV path for per-session scan summary. Default: {DEFAULT_SUMMARY_OUTPUT}",
    )
    parser.add_argument(
        "--threshold-hz",
        type=float,
        default=10.0,
        help="Minimum absolute aud-vs-vis quiescent rate difference in Hz.",
    )
    parser.add_argument(
        "--target-per-session",
        type=int,
        default=3,
        help="Stop scanning each NWB after this many matching units are found.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=64,
        help="Number of candidate units to load with spike times per batch.",
    )
    parser.add_argument(
        "--max-candidates-per-session",
        type=int,
        default=None,
        help="Optional hard cap on candidate units scanned per NWB.",
    )
    parser.add_argument(
        "--min-overall-rate-hz",
        type=float,
        default=2.0,
        help=(
            "Skip units with lower overall firing_rate metadata before loading "
            "spike times. Use 0 to disable."
        ),
    )
    parser.add_argument(
        "--include-sensory-cortex",
        action="store_true",
        help="Do not skip sensory cortical structures.",
    )
    parser.add_argument(
        "--session-id",
        action="append",
        default=None,
        help="Restrict to one or more session IDs. May be passed multiple times.",
    )
    parser.add_argument(
        "--hdf5",
        dest="zarr",
        action="store_false",
        help="Use HDF5 NWBs instead of the default Zarr assets.",
    )
    parser.set_defaults(zarr=True)
    return parser.parse_args()


def session_id_from_nwb_path(nwb_path: str | pathlib.Path) -> str:
    name = pathlib.PurePosixPath(str(nwb_path)).name
    for suffix in (".nwb.zarr", ".nwb.hdf5", ".nwb.h5", ".nwb"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def sensory_cortex_filter(prefixes: Iterable[str]) -> pl.Expr:
    structure = pl.col("structure").cast(pl.Utf8).fill_null("")
    return pl.any_horizontal([structure.str.starts_with(prefix) for prefix in prefixes])


def get_trials(nwb_path: str, *, zarr: bool) -> pl.DataFrame:
    return (
        nwb_access.scan_table("/intervals/trials", nwb_paths=(nwb_path,), zarr=zarr)
        .select(TRIAL_COLUMNS)
        .filter(
            pl.col("rewarded_modality").is_in(["aud", "vis"]),
            pl.col("quiescent_start_time").is_not_null(),
            pl.col("quiescent_stop_time").is_not_null(),
            ~pl.col("is_opto").fill_null(False),
        )
        .with_columns(
            (
                pl.col("quiescent_stop_time") - pl.col("quiescent_start_time")
            ).alias("quiescent_duration_s")
        )
        .filter(pl.col("quiescent_duration_s") > 0)
        .collect()
    )


def get_candidate_metadata(
    nwb_path: str,
    *,
    zarr: bool,
    include_sensory_cortex: bool,
    min_overall_rate_hz: float,
    max_candidates: int | None,
) -> pl.DataFrame:
    metadata = (
        nwb_access.scan_table(
            "/units",
            nwb_paths=(nwb_path,),
            zarr=zarr,
            exclude_array_columns=True,
        )
        .select(UNIT_METADATA_COLUMNS)
        .collect()
    )
    metadata = metadata.filter(pl.col("is_qc_pass"))

    if min_overall_rate_hz > 0:
        metadata = metadata.filter(
            pl.col("firing_rate").fill_null(0) >= min_overall_rate_hz
        )

    if not include_sensory_cortex:
        metadata = metadata.filter(~sensory_cortex_filter(SENSORY_CORTICAL_PREFIXES))

    metadata = metadata.sort("firing_rate", descending=True, nulls_last=True)
    if max_candidates is not None:
        metadata = metadata.head(max_candidates)
    return metadata


def iter_unit_batches(
    metadata: pl.DataFrame,
    nwb_path: str,
    *,
    zarr: bool,
    batch_size: int,
) -> Iterable[pl.DataFrame]:
    for start in range(0, metadata.height, batch_size):
        unit_ids = metadata["unit_id"].slice(start, batch_size).to_list()
        if not unit_ids:
            break
        yield (
            nwb_access.scan_table(
                "/units",
                nwb_paths=(nwb_path,),
                zarr=zarr,
                exclude_array_columns=False,
            )
            .filter(pl.col("unit_id").is_in(unit_ids))
            .select(UNIT_SPIKE_COLUMNS)
            .collect()
        )


def context_modulation_for_batch(
    units: pl.DataFrame,
    trials: pl.DataFrame,
) -> pl.DataFrame:
    counts = (
        units.vec.join_between(
            other=trials,
            values="spike_times",
            bounds=("quiescent_start_time", "quiescent_stop_time"),
            as_counts=True,
            check_sortedness=False,
        )
        .rename({"spike_times": "quiescent_spike_count"})
    )

    rates = (
        counts.group_by("unit_id", "rewarded_modality")
        .agg(
            pl.col("quiescent_spike_count").sum().alias("spike_count"),
            pl.col("quiescent_duration_s").sum().alias("duration_s"),
            pl.len().alias("n_trials"),
        )
        .with_columns(
            (pl.col("spike_count") / pl.col("duration_s")).alias(
                "quiescent_rate_hz"
            )
        )
    )

    aud = rates.filter(pl.col("rewarded_modality") == "aud").select(
        "unit_id",
        pl.col("spike_count").alias("aud_spike_count"),
        pl.col("duration_s").alias("aud_duration_s"),
        pl.col("n_trials").alias("aud_n_trials"),
        pl.col("quiescent_rate_hz").alias("aud_quiescent_rate_hz"),
    )
    vis = rates.filter(pl.col("rewarded_modality") == "vis").select(
        "unit_id",
        pl.col("spike_count").alias("vis_spike_count"),
        pl.col("duration_s").alias("vis_duration_s"),
        pl.col("n_trials").alias("vis_n_trials"),
        pl.col("quiescent_rate_hz").alias("vis_quiescent_rate_hz"),
    )
    unit_info = units.select(UNIT_METADATA_COLUMNS)
    return (
        unit_info.join(aud, on="unit_id", how="inner")
        .join(vis, on="unit_id", how="inner")
        .with_columns(
            (
                pl.col("aud_quiescent_rate_hz")
                - pl.col("vis_quiescent_rate_hz")
            ).alias("context_modulation_hz")
        )
        .with_columns(
            pl.col("context_modulation_hz").abs().alias(
                "abs_context_modulation_hz"
            ),
            pl.when(pl.col("context_modulation_hz") > 0)
            .then(pl.lit("aud"))
            .otherwise(pl.lit("vis"))
            .alias("higher_rate_context"),
        )
    )


def scan_session(
    nwb_path: str,
    *,
    zarr: bool,
    threshold_hz: float,
    target_per_session: int,
    batch_size: int,
    max_candidates_per_session: int | None,
    include_sensory_cortex: bool,
    min_overall_rate_hz: float,
) -> tuple[pl.DataFrame, dict[str, object]]:
    session_id = session_id_from_nwb_path(nwb_path)
    trials = get_trials(nwb_path, zarr=zarr)
    metadata = get_candidate_metadata(
        nwb_path,
        zarr=zarr,
        include_sensory_cortex=include_sensory_cortex,
        min_overall_rate_hz=min_overall_rate_hz,
        max_candidates=max_candidates_per_session,
    )

    hits: list[pl.DataFrame] = []
    n_scanned = 0
    n_batches = 0
    stopped_early = False

    for units in iter_unit_batches(
        metadata,
        nwb_path,
        zarr=zarr,
        batch_size=batch_size,
    ):
        n_batches += 1
        n_scanned += units.height
        metrics = context_modulation_for_batch(units, trials)
        batch_hits = metrics.filter(
            pl.col("abs_context_modulation_hz") >= threshold_hz
        )
        if not batch_hits.is_empty():
            hits.append(batch_hits)
        n_hits = sum(frame.height for frame in hits)
        print(
            f"{session_id}: scanned {n_scanned}/{metadata.height} candidates, "
            f"found {n_hits} hits",
            flush=True,
        )
        if n_hits >= target_per_session:
            stopped_early = True
            break

    if hits:
        session_hits = (
            pl.concat(hits, how="diagonal_relaxed")
            .with_columns(
                session_id=pl.lit(session_id),
                nwb_path=pl.lit(nwb_path),
            )
            .sort("abs_context_modulation_hz", descending=True)
            .head(target_per_session)
        )
    else:
        session_hits = pl.DataFrame()

    summary = {
        "session_id": session_id,
        "nwb_path": nwb_path,
        "candidate_units_available": metadata.height,
        "candidate_units_scanned": n_scanned,
        "batches_scanned": n_batches,
        "matching_units": session_hits.height,
        "stopped_early": stopped_early,
        "threshold_hz": threshold_hz,
        "target_per_session": target_per_session,
        "batch_size": batch_size,
        "min_overall_rate_hz": min_overall_rate_hz,
        "sensory_cortex_skipped": not include_sensory_cortex,
        "skipped_structure_prefixes": (
            "" if include_sensory_cortex else ";".join(SENSORY_CORTICAL_PREFIXES)
        ),
    }
    return session_hits, summary


def empty_results_df() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "session_id": pl.Utf8,
            "unit_id": pl.Utf8,
            "structure": pl.Utf8,
            "location": pl.Utf8,
            "firing_rate": pl.Float64,
            "activity_drift": pl.Float64,
            "is_not_drift": pl.Boolean,
            "is_qc_pass": pl.Boolean,
            "_nwb_path": pl.Utf8,
            "_table_index": pl.UInt32,
            "nwb_path": pl.Utf8,
            "aud_spike_count": pl.UInt32,
            "aud_duration_s": pl.Float64,
            "aud_n_trials": pl.UInt32,
            "aud_quiescent_rate_hz": pl.Float64,
            "vis_spike_count": pl.UInt32,
            "vis_duration_s": pl.Float64,
            "vis_n_trials": pl.UInt32,
            "vis_quiescent_rate_hz": pl.Float64,
            "context_modulation_hz": pl.Float64,
            "abs_context_modulation_hz": pl.Float64,
            "higher_rate_context": pl.Utf8,
        }
    )


def main() -> None:
    args = parse_args()
    nwb_paths = list(nwb_access.get_nwb_paths(zarr=args.zarr))
    if args.session_id:
        wanted = set(args.session_id)
        nwb_paths = [
            path for path in nwb_paths if session_id_from_nwb_path(path) in wanted
        ]
    if not nwb_paths:
        raise ValueError("No NWB paths matched the requested filters")

    all_hits: list[pl.DataFrame] = []
    summaries: list[dict[str, object]] = []

    for nwb_path in nwb_paths:
        session_id = session_id_from_nwb_path(nwb_path)
        print(f"Scanning {session_id}", flush=True)
        hits, summary = scan_session(
            nwb_path,
            zarr=args.zarr,
            threshold_hz=args.threshold_hz,
            target_per_session=args.target_per_session,
            batch_size=args.batch_size,
            max_candidates_per_session=args.max_candidates_per_session,
            include_sensory_cortex=args.include_sensory_cortex,
            min_overall_rate_hz=args.min_overall_rate_hz,
        )
        summaries.append(summary)
        if not hits.is_empty():
            all_hits.append(hits)

    results = (
        pl.concat(all_hits, how="diagonal_relaxed")
        if all_hits
        else empty_results_df()
    )
    if not results.is_empty():
        results = results.select(empty_results_df().columns).sort(
            "session_id", "abs_context_modulation_hz", descending=[False, True]
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    results.write_csv(args.output)
    pl.DataFrame(summaries).write_csv(args.summary_output)

    print(f"Wrote {results.height} matching units to {args.output}", flush=True)
    print(f"Wrote scan summary to {args.summary_output}", flush=True)


if __name__ == "__main__":
    main()

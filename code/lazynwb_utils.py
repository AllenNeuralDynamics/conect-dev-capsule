from __future__ import annotations

import altair as alt
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import pandas as pd
import polars as pl

import pynwb_utils


_CCF_COORDINATE_COLS = ("ccf_ap", "ccf_ml", "ccf_dv")
_TOOLTIP_COLS = ("structure", "unit_id", "is_qc_pass", "electrode_group_name")
_CCF_REQUIRED_COLS = (*_TOOLTIP_COLS, *_CCF_COORDINATE_COLS)
_TRIAL_COLUMNS = pynwb_utils._TRIAL_COLUMNS


def _existing_columns(
    columns: tuple[str, ...] | list[str],
    available_columns: set[str],
) -> list[str]:
    return [column for column in columns if column in available_columns]


def _to_pandas(df: pd.DataFrame | pl.DataFrame) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df
    return df.to_pandas()


def _filter_not_noise(lf: pl.LazyFrame, columns: set[str]) -> pl.LazyFrame:
    if "decoder_label" not in columns:
        return lf
    return lf.filter(
        pl.col("decoder_label").is_null() | (pl.col("decoder_label") != "noise")
    )


def _collect_ccf_units(units_lf: pl.LazyFrame) -> pl.DataFrame:
    columns = set(units_lf.collect_schema().names())
    select_columns = _existing_columns(_CCF_REQUIRED_COLS, columns)
    ccf_columns = _existing_columns(_CCF_COORDINATE_COLS, columns)

    query = _filter_not_noise(units_lf, columns).select(select_columns)
    if ccf_columns:
        query = query.unique(subset=ccf_columns)
    return query.collect()


def _prepare_ccf_units(
    units: pd.DataFrame | pl.DataFrame | pl.LazyFrame,
) -> pd.DataFrame:
    if isinstance(units, pl.LazyFrame):
        return _to_pandas(_collect_ccf_units(units))

    if isinstance(units, pl.DataFrame):
        return _to_pandas(_collect_ccf_units(units.lazy()))

    columns = set(units.columns)
    select_columns = _existing_columns(_CCF_REQUIRED_COLS, columns)
    ccf_columns = _existing_columns(_CCF_COORDINATE_COLS, columns)

    units_pd = units
    if "decoder_label" in columns:
        units_pd = units_pd[
            units_pd["decoder_label"].isna() | (units_pd["decoder_label"] != "noise")
        ]
    units_pd = units_pd.loc[:, select_columns].copy()
    if ccf_columns:
        units_pd = units_pd.drop_duplicates(subset=ccf_columns)
    return units_pd


def plot_ccf_coordinates(
    units_df_or_lf_or_nwb,
    *,
    title: str = "Allen CCF coordinates of Neuropixels recording sites",
) -> alt.ConcatChart:
    """Return an Altair chart for CCF coordinate projections.

    ``pl.LazyFrame`` inputs are filtered for non-noise units, projected to the
    plotting columns, deduplicated by CCF coordinates, and only then collected.
    Non-lazy inputs are passed through the original ``pynwb_utils`` plotting
    implementation.
    """
    if isinstance(
        units_df_or_lf_or_nwb,
        (pd.DataFrame, pl.DataFrame, pl.LazyFrame),
    ):
        units_df = _prepare_ccf_units(units_df_or_lf_or_nwb)
        return pynwb_utils.plot_ccf_coordinates(units_df, title=title)

    return pynwb_utils.plot_ccf_coordinates(units_df_or_lf_or_nwb, title=title)


def _collect_raster_units(
    units_lf: pl.LazyFrame,
    unit_id: str,
    *,
    include_spike_times: bool,
) -> pl.DataFrame:
    columns = set(units_lf.collect_schema().names())
    requested_columns = ["unit_id", "location"]
    if include_spike_times:
        requested_columns.append("spike_times")

    query = units_lf
    if "unit_id" in columns:
        query = query.filter(pl.col("unit_id") == unit_id)
    return query.select(_existing_columns(requested_columns, columns)).collect()


def _prepare_raster_units(
    units: pd.DataFrame | pl.DataFrame | pl.LazyFrame,
    unit_id: str,
    *,
    include_spike_times: bool,
) -> pd.DataFrame:
    if isinstance(units, pl.LazyFrame):
        return _to_pandas(
            _collect_raster_units(
                units,
                unit_id,
                include_spike_times=include_spike_times,
            )
        )

    requested_columns = ["unit_id", "location"]
    if include_spike_times:
        requested_columns.append("spike_times")

    if isinstance(units, pl.DataFrame):
        columns = set(units.columns)
        units_df = units
        if "unit_id" in columns:
            units_df = units_df.filter(pl.col("unit_id") == unit_id)
        return _to_pandas(
            units_df.select(_existing_columns(requested_columns, columns))
        )

    columns = set(units.columns)
    units_df = units
    if "unit_id" in columns:
        units_df = units_df[units_df["unit_id"] == unit_id]
    return units_df.loc[:, _existing_columns(requested_columns, columns)].copy()


def _collect_raster_trials(
    trials_lf: pl.LazyFrame,
    stim_names: tuple[str, ...],
) -> pl.DataFrame:
    columns = set(trials_lf.collect_schema().names())

    query = trials_lf
    if "stim_name" in columns:
        query = query.filter(pl.col("stim_name").is_in(stim_names))
    return query.select(_existing_columns(list(_TRIAL_COLUMNS), columns)).collect()


def _prepare_raster_trials(
    trials: pd.DataFrame | pl.DataFrame | pl.LazyFrame,
    stim_names,
) -> pd.DataFrame:
    stim_names = tuple(stim_names)

    if isinstance(trials, pl.LazyFrame):
        return _to_pandas(_collect_raster_trials(trials, stim_names))

    if isinstance(trials, pl.DataFrame):
        columns = set(trials.columns)
        trials_df = trials
        if "stim_name" in columns:
            trials_df = trials_df.filter(pl.col("stim_name").is_in(stim_names))
        return _to_pandas(
            trials_df.select(_existing_columns(list(_TRIAL_COLUMNS), columns))
        )

    columns = set(trials.columns)
    trials_df = trials
    if "stim_name" in columns:
        trials_df = trials_df[trials_df["stim_name"].isin(stim_names)]
    return trials_df.loc[:, _existing_columns(list(_TRIAL_COLUMNS), columns)].copy()


def plot_unit_raster_psth(
    unit_id: str,
    nwb_or_units_df,
    trials_df: pd.DataFrame | pl.DataFrame | pl.LazyFrame | None = None,
    unit_spike_times: npt.NDArray[np.floating] | None = None,
    stim_names=("vis+", "aud+", "vis-", "aud-"),
    with_instruction_trial_whitespace: bool = True,
    max_psth_spike_rate: float = 60,
    rewarded_context_colors: dict[str, str] | None = None,
    show_event_marker_legend: bool = True,
    xlim_min: float = -1.0,
    xlim_max: float = 2.0,
) -> plt.Figure:
    """Raster plot + PSTH for one unit, accepting lazy units/trials tables.

    When ``nwb_or_units_df`` is a ``pl.LazyFrame``, the units table is filtered
    to ``unit_id`` and projected to ``unit_id``, ``location``, and optionally
    ``spike_times`` before collection. Lazy trials are filtered to ``stim_names``
    and projected to the plotting columns before collection.
    """
    if isinstance(nwb_or_units_df, (pd.DataFrame, pl.DataFrame, pl.LazyFrame)):
        if trials_df is None:
            raise ValueError("trials_df must be provided when passing a units table")

        units_df = _prepare_raster_units(
            nwb_or_units_df,
            unit_id,
            include_spike_times=unit_spike_times is None,
        )
        trials_df = _prepare_raster_trials(trials_df, stim_names)

        return pynwb_utils.plot_unit_raster_psth(
            unit_id=unit_id,
            nwb_or_units_df=units_df,
            trials_df=trials_df,
            unit_spike_times=unit_spike_times,
            stim_names=stim_names,
            with_instruction_trial_whitespace=with_instruction_trial_whitespace,
            max_psth_spike_rate=max_psth_spike_rate,
            rewarded_context_colors=rewarded_context_colors,
            show_event_marker_legend=show_event_marker_legend,
            xlim_min=xlim_min,
            xlim_max=xlim_max,
        )

    return pynwb_utils.plot_unit_raster_psth(
        unit_id=unit_id,
        nwb_or_units_df=nwb_or_units_df,
        trials_df=trials_df,
        unit_spike_times=unit_spike_times,
        stim_names=stim_names,
        with_instruction_trial_whitespace=with_instruction_trial_whitespace,
        max_psth_spike_rate=max_psth_spike_rate,
        rewarded_context_colors=rewarded_context_colors,
        show_event_marker_legend=show_event_marker_legend,
        xlim_min=xlim_min,
        xlim_max=xlim_max,
    )


__all__ = ["plot_ccf_coordinates", "plot_unit_raster_psth"]

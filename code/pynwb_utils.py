from __future__ import annotations

import logging

import matplotlib.patches as patches
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import numpy.typing as npt
import pandas as pd
import polars as pl
import altair as alt

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
plt.rcParams["font.family"] = "Arial"
plt.rcParams["font.size"] = 8
plt.rcParams["pdf.fonttype"] = 42

_RASTER_DEFAULT_CONTEXT_COLORS = {"vis": "#1f77b4", "aud": "#ff7f0e"}
_RASTER_INSTRUCTION_COLOR = "#6FA23A"
_RASTER_EVENT_COLORS = {"hit": "#00A59B", "false_alarm": "#CD0F55"}

_TRIAL_COLUMNS = (
    "block_index",
    "is_aud_rewarded",
    "is_false_alarm",
    "is_reward_scheduled",
    "is_rewarded",
    "is_response",
    "is_vis_rewarded",
    "response_time",
    "reward_time",
    "rewarded_modality",
    "start_time",
    "stim_name",
    "stim_start_time",
    "stop_time",
    "task_control_response_time",
    "trial_index_in_block",
)

CCF_COLORS_URL = "https://raw.githubusercontent.com/cortex-lab/allenCCF/refs/heads/master/structure_tree_safe_2017.csv"

_CCF_COORDINATE_COLS = ["ccf_ap", "ccf_ml", "ccf_dv"]
_TOOLTIP_COLS = ["structure", "unit_id", "is_qc_pass", "electrode_group_name"]
_PIXELS_PER_MM = 65


def plot_ccf_coordinates(
    units_df_or_nwb,
    *,
    title: str = "Allen CCF coordinates of Neuropixels recording sites",
) -> alt.ConcatChart:
    """Return an Altair chart of AP/DV and ML/DV CCF coordinate projections.

    Parameters
    ----------
    units_df_or_nwb:
        Either a pandas DataFrame with unit metadata (must contain columns
        ``structure``, ``unit_id``, ``is_qc_pass``, ``ccf_ap``, ``ccf_ml``,
        ``ccf_dv``, ``electrode_group_name``), or a ``pynwb.NWBFile`` from
        which the units table is extracted automatically.
    title:
        Chart title.
    """
    # ------------------------------------------------------------------ #
    # 1. Resolve units_df
    # ------------------------------------------------------------------ #
    if isinstance(units_df_or_nwb, pd.DataFrame):
        units_df = units_df_or_nwb
    else:
        # Assume pynwb.NWBFile
        units_df = units_df_or_nwb.units.to_dataframe(
            exclude={"waveform_mean", "waveform_sd"}
        )

    # Work with only the columns we need so the chart data stays small
    cols = [c for c in _TOOLTIP_COLS + _CCF_COORDINATE_COLS if c in units_df.columns]
    unit_ccf = units_df[cols].copy()

    # CCF coordinates are stored in microns; convert to millimetres
    for col in _CCF_COORDINATE_COLS:
        if col in unit_ccf.columns:
            unit_ccf[col] = unit_ccf[col] / 1000.0

    # Deduplicate by unique locations (CCF coordinates)
    unit_ccf = unit_ccf.drop_duplicates(subset=_CCF_COORDINATE_COLS)

    # Exclude noise units
    if "decoder_label" in unit_ccf.columns:
        unit_ccf = unit_ccf[unit_ccf["decoder_label"] != "noise"]

    # ------------------------------------------------------------------ #
    # 2. Build structure → hex-colour mapping from Allen CCF reference CSV
    # ------------------------------------------------------------------ #
    ccf_colors = (
        pd.read_csv(CCF_COLORS_URL, usecols=["acronym", "color_hex_triplet"])
        .drop_duplicates("acronym")
    )

    color_map = (
        unit_ccf[["structure"]]
        .drop_duplicates()
        .merge(ccf_colors, left_on="structure", right_on="acronym", how="left")
        .assign(
            color_hex_triplet=lambda df: "#"
            + df["color_hex_triplet"].fillna("999999")
        )
        .sort_values("structure")
    )

    domain = color_map["structure"].tolist()
    color_range = color_map["color_hex_triplet"].tolist()
    color_scale = alt.Scale(domain=domain, range=color_range)

    # ------------------------------------------------------------------ #
    # 3. Axis / domain helpers
    # ------------------------------------------------------------------ #
    def padded_domain(series: pd.Series, padding: float = 0.1, min_span: float | None = None) -> list[float]:
        lo = float(series.min()) - padding
        hi = float(series.max()) + padding
        if min_span is not None and hi - lo < min_span:
            center = (lo + hi) / 2
            lo = center - min_span / 2
            hi = center + min_span / 2
        return [lo, hi]

    def domain_pixels(dom: list[float]) -> int:
        return max(1, round((dom[1] - dom[0]) * _PIXELS_PER_MM))

    ccf_ap_domain = padded_domain(unit_ccf["ccf_ap"], min_span=2.0)
    ccf_ml_domain = padded_domain(unit_ccf["ccf_ml"], min_span=2.0)
    ccf_dv_domain = padded_domain(unit_ccf["ccf_dv"])

    axis_gap = "\u00a0" * 20
    x_axis_ap = alt.Axis(title=f"← anterior{axis_gap}(mm){axis_gap}posterior →")
    x_axis_ml = alt.Axis(title=f"← medial{axis_gap}(mm){axis_gap}lateral →")
    y_axis_dv = alt.Axis(title=f"← dorsal{axis_gap}(mm){axis_gap}ventral →")

    # ------------------------------------------------------------------ #
    # 4. Build chart
    # ------------------------------------------------------------------ #
    base = (
        alt.Chart(unit_ccf)
        .mark_point()
        .encode(
            tooltip=[c for c in _TOOLTIP_COLS if c in unit_ccf.columns],
            color=alt.Color("structure", scale=color_scale, legend=None),
        )
    )

    ap_projection = base.encode(
        x=alt.X("ccf_ap", axis=x_axis_ap, scale=alt.Scale(domain=ccf_ap_domain, nice=False)),
        y=alt.Y("ccf_dv", axis=y_axis_dv, scale=alt.Scale(domain=ccf_dv_domain, nice=False, reverse=True)),
    ).properties(
        width=domain_pixels(ccf_ap_domain),
        height=domain_pixels(ccf_dv_domain),
    )

    ml_projection = base.encode(
        x=alt.X("ccf_ml", axis=x_axis_ml, scale=alt.Scale(domain=ccf_ml_domain, nice=False, reverse=True)),
        y=alt.Y("ccf_dv", axis=y_axis_dv, scale=alt.Scale(domain=ccf_dv_domain, nice=False, reverse=True)),
    ).properties(
        width=domain_pixels(ccf_ml_domain),
        height=domain_pixels(ccf_dv_domain),
    )

    return (ap_projection | ml_projection).properties(title=title)


# ---------------------------------------------------------------------------
# Raster + PSTH plot
# ---------------------------------------------------------------------------

def _make_psth(
    spikes: npt.NDArray[np.floating],
    start_times: npt.NDArray[np.floating],
    window_dur: float,
    bin_size: float,
) -> tuple[npt.NDArray[np.floating], npt.NDArray[np.floating]]:
    bin_edges = np.arange(0, window_dur + bin_size, bin_size)
    counts = np.zeros(len(bin_edges) - 1, dtype=float)
    if not len(start_times):
        return counts, bin_edges[:-1]
    for start_time in start_times:
        start = np.searchsorted(spikes, start_time, side="left")
        stop = np.searchsorted(spikes, start_time + window_dur, side="left")
        counts += np.histogram(spikes[start:stop] - start_time, bins=bin_edges)[0]
    spike_rate_hz = counts / (len(start_times) * bin_size)
    return spike_rate_hz, bin_edges[:-1]


def plot_unit_raster_psth(
    unit_id: str,
    nwb_or_units_df,
    trials_df: pd.DataFrame | None = None,
    unit_spike_times: npt.NDArray[np.floating] | None = None,
    stim_names=("vis+", "aud+", "vis-", "aud-"),
    with_instruction_trial_whitespace: bool = True,
    max_psth_spike_rate: float = 60,
    rewarded_context_colors: dict[str, str] | None = None,
    show_event_marker_legend: bool = True,
    xlim_min: float = -1.0,
    xlim_max: float = 2.0,
) -> plt.Figure:
    """Raster plot + PSTH for a single unit across stimulus types and blocks.

    Parameters
    ----------
    unit_id:
        Identifier matching the ``unit_id`` column in the units table.
    nwb_or_units_df:
        A ``pynwb.NWBFile`` (trials and units are read from it automatically),
        or a pandas ``DataFrame`` of units (in which case *trials_df* must also
        be provided).
    trials_df:
        Required when *nwb_or_units_df* is a DataFrame.
    unit_spike_times:
        Pre-extracted spike times array.  Read from the units table if omitted.
    """
    rewarded_context_colors = (
        _RASTER_DEFAULT_CONTEXT_COLORS
        if rewarded_context_colors is None
        else rewarded_context_colors
    )

    # ------------------------------------------------------------------ #
    # Resolve input data
    # ------------------------------------------------------------------ #
    if isinstance(nwb_or_units_df, pd.DataFrame):
        if trials_df is None:
            raise ValueError("trials_df must be provided when passing a units DataFrame")
        units_pd = nwb_or_units_df
        trials_pd = trials_df
    else:
        # pynwb.NWBFile
        units_pd = nwb_or_units_df.units.to_dataframe()
        trials_pd = nwb_or_units_df.trials[:]

    # Convert trials to polars for internal manipulation
    trials = pl.from_pandas(trials_pd.reset_index(drop=True))
    # Add any TRIAL_COLUMNS that are missing (as nulls) so later code is safe
    for col in _TRIAL_COLUMNS:
        if col not in trials.columns:
            trials = trials.with_columns(pl.lit(None).alias(col))
    trials = trials.select(list(_TRIAL_COLUMNS))

    unit_row = units_pd[units_pd["unit_id"] == unit_id] if "unit_id" in units_pd.columns else pd.DataFrame()

    if unit_spike_times is None:
        if unit_row.empty or "spike_times" not in unit_row.columns:
            raise ValueError(f"No spike times found for unit {unit_id!r}")
        unit_spike_times = np.asarray(unit_row["spike_times"].iloc[0], dtype=float)
    else:
        unit_spike_times = np.asarray(unit_spike_times, dtype=float)

    pad_start = -xlim_min + 0.5
    if trials.is_empty():
        raise ValueError(f"No trials found for unit {unit_id!r}")
    if not unit_spike_times.size:
        raise ValueError(f"No spike times found for {unit_id}")

    modality_to_rewarded_stim = {"aud": "aud+", "vis": "vis+"}

    # Assign spike times to each trial window
    spike_times_by_trial = tuple(
        (
            unit_spike_times[slice(start, stop)]
            if 0 <= start < stop <= len(unit_spike_times)
            else []
        )
        for start, stop in np.searchsorted(
            unit_spike_times,
            trials.select(pl.col("start_time") - pad_start, "stop_time"),
        )
    )
    if not spike_times_by_trial or not any(len(a) for a in spike_times_by_trial):
        raise ValueError(f"No spike times matched trial windows for {unit_id}")

    trials = (
        trials.with_columns(
            pl.Series(
                name="spike_times",
                values=spike_times_by_trial,
                dtype=pl.List(pl.Float64),
            ),
        )
        .with_row_index()
        .explode("spike_times")
        .with_columns(
            stim_centered_spike_times=(
                pl.col("spike_times") - pl.col("stim_start_time")
            )
        )
        .group_by(
            pl.all().exclude("spike_times", "stim_centered_spike_times"),
            maintain_order=True,
        )
        .all()
        .filter(pl.col("stim_name").is_in(stim_names))
    )

    # Create dummy instruction trials for non-rewarded stimuli (block alignment)
    trials_: pl.DataFrame = trials
    if with_instruction_trial_whitespace:
        for block_index in trials_["block_index"].unique():
            rewarded_modality = trials_.filter(pl.col("block_index") == block_index)["rewarded_modality"][0]
            autorewarded_stim = modality_to_rewarded_stim[rewarded_modality]
            for stim_name in stim_names:
                if autorewarded_stim == stim_name:
                    continue
                extra_df = trials.filter(
                    pl.col("block_index") == block_index,
                    pl.col("is_reward_scheduled"),
                    pl.col("trial_index_in_block") <= 5,
                ).with_columns(
                    stim_name=pl.lit(stim_name),
                    is_response=pl.lit(False),
                    is_rewarded=pl.lit(False),
                    stim_centered_spike_times=pl.lit([]),
                )
                trials_ = pl.concat([trials_, extra_df])

    trials_ = trials_.sort("start_time").with_columns(
        is_new_block=(
            pl.col("start_time") == pl.col("start_time").min().over("stim_name", "block_index")
        ),
        num_trials_in_block=pl.col("start_time").count().over("stim_name", "block_index"),
    )

    line_params = {"color": "grey", "lw": 0.3}
    response_window_start_time = 0.1
    response_window_stop_time = 1.0
    instruction_patch_params = {"color": _RASTER_INSTRUCTION_COLOR, "alpha": 0.22, "lw": 0, "zorder": -1}

    add_psth = True
    nominal_rows_per_block = 20
    block_height_on_page = (6 + add_psth) * nominal_rows_per_block / trials_.n_unique("block_index")

    fig, axes = plt.subplots(1, len(stim_names), figsize=(1.5 * len(stim_names), 6 + add_psth), sharey=True)
    axes = np.atleast_1d(axes)
    last_ypos: list[float] = []

    for ax, stim in zip(axes, stim_names):
        stim_trials = trials_.filter(pl.col("stim_name") == stim)
        idx_in_block = 0
        for _idx, trial in enumerate(stim_trials.iter_rows(named=True)):
            num_instructed_trials = max(
                len(
                    trials.filter(
                        pl.col("block_index") == trial["block_index"],
                        pl.col(f"is_{c}_rewarded"),
                        pl.col("is_reward_scheduled"),
                        pl.col("trial_index_in_block") < 14,
                    )
                )
                for c in ("aud", "vis")
            )
            is_vis_block: bool = "vis" in trial["rewarded_modality"]
            is_vis_target: bool = "vis+" in trial["stim_name"]
            is_aud_target: bool = "aud+" in trial["stim_name"]
            is_rewarded_stim: bool = (is_vis_target and is_vis_block) or (is_aud_target and not is_vis_block)

            if trial["is_new_block"]:
                idx_in_block = 0
                block_df = stim_trials.filter(pl.col("block_index") == trial["block_index"])
                ypositions = (
                    np.linspace(0, block_height_on_page, len(block_df), endpoint=False)
                    + trial["block_index"] * block_height_on_page
                )
                halfline = 0.5 * np.diff(ypositions).mean()

            ypos = ypositions[idx_in_block]
            idx_in_block += 1

            if trial["is_new_block"]:
                if ax is axes[0]:
                    ax.text(
                        x=xlim_min - 0.6,
                        y=ypositions[0] + block_height_on_page // 2,
                        s=trial["rewarded_modality"],
                        fontsize=8,
                        ha="center",
                        va="center",
                        color=rewarded_context_colors[trial["rewarded_modality"]],
                    )
                if trial["block_index"] > 0:
                    ax.axhline(y=ypos - halfline, **line_params, zorder=99)
                if is_rewarded_stim:
                    ax.axhspan(
                        ymin=max(ypos, 0) - halfline,
                        ymax=ypositions[num_instructed_trials - 1] + halfline,
                        **instruction_patch_params,
                    )
                rect = patches.Rectangle(
                    xy=(
                        response_window_start_time,
                        (
                            y0 := (
                                ypos if is_rewarded_stim or not with_instruction_trial_whitespace
                                else ypositions[min(num_instructed_trials, len(block_df) - 1)]
                            )
                            - halfline
                        ),
                    ),
                    width=response_window_stop_time - response_window_start_time,
                    height=(ypositions[-1] + halfline) - y0,
                    linewidth=0,
                    edgecolor="none",
                    facecolor=[0.9, 0.9, 0.9, 0.5],
                    zorder=20,
                )
                ax.add_patch(rect)

            if trial["is_reward_scheduled"] and trial["trial_index_in_block"] > 10:
                ax.axhspan(ypos - halfline, ypos + halfline, **instruction_patch_params)

            # Raster ticks
            trial_spike_times = np.array(trial["stim_centered_spike_times"])
            if not (trial_spike_times.size == 1 and trial_spike_times[0] is None):
                ax.eventplot(
                    positions=trial_spike_times,
                    lineoffsets=ypos,
                    linewidths=0.3,
                    linelengths=0.8,
                    color=[0.45] * 3,
                    zorder=99,
                )

            # Outcome markers
            if trial["is_rewarded"]:
                ax.scatter(
                    [trial["reward_time"] - trial["stim_start_time"]],
                    [ypos],
                    marker="o", s=9, facecolors="none",
                    edgecolors=_RASTER_EVENT_COLORS["hit"], linewidths=0.45, zorder=100,
                )
                continue
            elif trial["is_false_alarm"]:
                response_t = trial["response_time"]
                if response_t is None:
                    continue
                ax.scatter(
                    [response_t - trial["stim_start_time"]],
                    [ypos],
                    marker="^", s=10, facecolors="none",
                    edgecolors=_RASTER_EVENT_COLORS["false_alarm"], linewidths=0.45, zorder=100,
                )
                continue

        last_ypos.append(ypos)

    # Format axes and add PSTH above raster
    for ax, stim in zip(axes, stim_names):
        if add_psth:
            bin_size_s = 25 / 1000
            scale_bar_len = max(1, int(max_psth_spike_rate / 4))
            ypad = 5
            ymin = max(last_ypos) + ypad
            ymax = ymin + nominal_rows_per_block
            ypos = ymax + 0.5

            def add_psth_plot(hist, bin_edges, **kwargs):
                norm = (hist / max_psth_spike_rate) * (ymax - ymin)
                ax.plot(bin_edges + np.diff(bin_edges)[0] / 2, ymax - norm, **kwargs)

            for rewarded_modality in ("aud", "vis"):
                color = rewarded_context_colors[rewarded_modality]
                hist_results = []
                for _, block_trials in trials.group_by("block_index"):
                    df = block_trials.filter(
                        pl.col(f"is_{rewarded_modality}_rewarded"),
                        pl.col("stim_name") == stim,
                    )
                    if not df["stim_centered_spike_times"].to_numpy().size:
                        continue
                    hist, bin_edges = _make_psth(
                        spikes=np.sort(unit_spike_times),
                        start_times=np.array(df["stim_start_time"] - pad_start),
                        window_dur=pad_start + xlim_max,
                        bin_size=bin_size_s,
                    )
                    bin_edges = bin_edges - pad_start
                    hist_results.append(hist)
                    add_psth_plot(hist, bin_edges, lw=0.3, c=color, alpha=0.3)
                if hist_results:
                    add_psth_plot(np.mean(hist_results, axis=0), bin_edges, lw=0.75, c=color)

            ax.add_patch(patches.Rectangle(
                xy=(response_window_start_time, ymin),
                width=response_window_stop_time - response_window_start_time,
                height=ymax - ymin + 0.5,
                linewidth=0, edgecolor="none", facecolor=[0.9, 0.9, 0.9, 0.5], zorder=-1,
            ))
            if ax is axes[0]:
                length = (ymax - ymin) * scale_bar_len / max_psth_spike_rate
                ax.plot([xlim_min - 0.1] * 2, [ymax - length, ymax], c="k", lw=1, clip_on=False)
                ax.text(xlim_min - 0.6, ymax - length / 2, f"{scale_bar_len} Hz",
                        fontsize=6, ha="center", va="center")

        ax.axvline(x=0, **line_params)
        ax.set_xlim(xlim_min, xlim_max)
        ax.set_ylim(-0.5, max(ypos, *last_ypos) + 0.5)
        ax.set_xticks(sorted({min(xlim_min, 0), 0, xlim_max}))
        ax.xaxis.set_tick_params(labelsize=6)
        ax.set_yticks([])
        if ax is axes[0]:
            ax.set_ylabel("trials")
            ax.yaxis.set_label_coords(x=-0.48, y=0.5)
            ax.annotate(
                "",
                xy=(-0.38, 0.42), xytext=(-0.38, 0.58),
                xycoords="axes fraction", textcoords="axes fraction",
                arrowprops={"arrowstyle": "->", "color": "black", "linewidth": 0.8,
                            "mutation_scale": 8, "shrinkA": 0, "shrinkB": 0},
                annotation_clip=False,
            )
            ax.text(xlim_min - 0.9, 0, "Rewarded\nmodality", fontsize=8, ha="center", va="center")
        ax.set_xlabel("time from\nstimulus onset (s)")
        ax.invert_yaxis()
        ax.set_aspect(0.1 * (xlim_max - xlim_min) / 3)
        ax.set_title(stim, fontsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.set_zorder(199)

    if unit_row.empty:
        location = "not in units df"
    elif "location" in unit_row.columns:
        location = unit_row["location"].iloc[0]
    else:
        location = "no CCF location (unannotated)"

    fig.set_dpi(300)
    fig.suptitle(f"unit_id = {unit_id} | location = {location}", fontsize=10)

    if show_event_marker_legend:
        fig.legend(
            handles=[
                Line2D([], [], marker="o", linestyle="none", markerfacecolor="none",
                       markeredgecolor=_RASTER_EVENT_COLORS["hit"], markeredgewidth=0.5,
                       markersize=4, label="hit"),
                Line2D([], [], marker="^", linestyle="none", markerfacecolor="none",
                       markeredgecolor=_RASTER_EVENT_COLORS["false_alarm"], markeredgewidth=0.5,
                       markersize=4, label="false alarm"),
            ],
            loc="upper right", bbox_to_anchor=(0.99, 0.985), frameon=False,
            fontsize=7, handletextpad=0.4, borderaxespad=0, labelspacing=0.25,
        )
    return fig

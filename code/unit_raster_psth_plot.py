# aligned blocks - standalone
from __future__ import annotations

import logging
import pathlib
from collections.abc import Iterable

import matplotlib.patches as patches
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import numpy.typing as npt
import polars as pl

import nwb_access

logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
plt.rcParams["font.family"] = "Arial"
plt.rcParams["font.size"] = 8
plt.rcParams["pdf.fonttype"] = 42

DEFAULT_REWARDED_CONTEXT_COLORS = {"vis": "#6464FF", "aud": "#CD0F55"}


class NoSpikesInTrialsError(ValueError):
    pass


TRIAL_COLUMNS = (
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


def _get_trials(
    unit_id: str,
    *,
    zarr: bool,
) -> pl.DataFrame:
    return (
        nwb_access.scan_table(
            "/intervals/trials",
            unit_id=unit_id,
            zarr=zarr,
        )
        .select(TRIAL_COLUMNS)
        .collect()
    )


def _get_unit(
    unit_id: str,
    include_spike_times: bool,
    *,
    zarr: bool,
) -> pl.DataFrame:
    columns = ["unit_id", "location", "structure", "_nwb_path", "_table_index"]
    if include_spike_times:
        columns.append("spike_times")
    session_id = nwb_access.session_id_from_unit_id(unit_id)
    unit = (
        nwb_access.scan_table(
            "/units",
            unit_id=unit_id,
            zarr=zarr,
            exclude_array_columns=not include_spike_times,
        )
        .filter(pl.col("unit_id") == unit_id)
        .select(columns)
        .collect()
    )
    if unit.is_empty():
        raise ValueError(f"No unit found for {unit_id!r}")
    return unit


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


def plot(
    unit_id: str,
    unit_spike_times: npt.NDArray[np.floating] | None = None,
    stim_names=("vis1", "sound1", "vis2", "sound2"),
    with_instruction_trial_whitespace: bool = False,
    max_psth_spike_rate: float = 60,  # Hz
    rewarded_context_colors: dict[str, str] | None = None,
    show_event_marker_legend: bool = True,
    zarr: bool = True,
    xlim_min=-1.0,  # seconds before stim onset
    xlim_max=2.0,  # seconds after stim onset
) -> plt.Figure:
    rewarded_context_colors = (
        DEFAULT_REWARDED_CONTEXT_COLORS
        if rewarded_context_colors is None
        else rewarded_context_colors
    )
    session_id = nwb_access.session_id_from_unit_id(unit_id)
    trials = _get_trials(unit_id, zarr=zarr)
    unit = _get_unit(
        unit_id,
        include_spike_times=unit_spike_times is None,
        zarr=zarr,
    )
    if unit_spike_times is None:
        unit_spike_times = np.asarray(unit["spike_times"][0], dtype=float)
    else:
        unit_spike_times = np.asarray(unit_spike_times, dtype=float)

    pad_start = -xlim_min + 0.5  # seconds before stim onset
    if trials.is_empty():
        raise ValueError(f"No trials found for {session_id}")
    if not unit_spike_times.size:
        raise NoSpikesInTrialsError(f"No spike times found for {unit_id}")
    modality_to_rewarded_stim = {"aud": "sound1", "vis": "vis1"}
    # add spikes to trials:
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
        raise NoSpikesInTrialsError(
            f"No spike times found matching trial times {unit} - either no task presented or major timing issue"
        )
    trials = (
        trials.with_columns(
            pl.Series(
                name="spike_times",
                values=spike_times_by_trial,
                dtype=pl.List(pl.Float64),
            ),  # doesn't handle empty entries well without explicit dtype
        )
        .with_row_index()
        .explode("spike_times")
        .with_columns(
            stim_centered_spike_times=(
                pl.col("spike_times")
                - pl.col("stim_start_time").alias("stim_centered_spike_times")
            )
        )
        .group_by(
            pl.all().exclude("spike_times", "stim_centered_spike_times"),
            maintain_order=True,
        )
        .all()
        .filter(
            pl.col("stim_name").is_in(stim_names),
            #! filter out autoreward trials triggered by 10 misses:
            # (pl.col('is_reward_scheduled').eq(True) & (pl.col('trial_index_in_block') < 5)) | pl.col('is_reward_scheduled').eq(False),
        )
    )

    # create dummy instruction trials for the non-rewarded stimuli for easier
    # alignment of blocks:
    trials_: pl.DataFrame = trials
    if with_instruction_trial_whitespace:
        for block_index in trials_["block_index"].unique():
            rewarded_modality = trials_.filter(pl.col("block_index") == block_index)[
                "rewarded_modality"
            ][0]
            autorewarded_stim = modality_to_rewarded_stim[rewarded_modality]
            for stim_name in stim_names:
                if autorewarded_stim == stim_name:
                    continue
                extra_df = trials.filter(  # filter original trials, not modified ones with dummy instruction trials
                    pl.col("block_index") == block_index,
                    pl.col("is_reward_scheduled"),
                    pl.col("trial_index_in_block")
                    <= 5,  # after 10 misses, an instruction trial is triggered: we don't want to duplicate these
                ).with_columns(
                    # switch the stim name:
                    stim_name=pl.lit(stim_name),
                    # make sure there's no info that will trigger plotting:
                    is_response=pl.lit(False),
                    is_rewarded=pl.lit(False),
                    stim_centered_spike_times=pl.lit([]),
                )
                trials_ = pl.concat([trials_, extra_df])

    # add columns for easier parsing of block structure:
    trials_ = trials_.sort("start_time").with_columns(
        is_new_block=(
            pl.col("start_time")
            == pl.col("start_time").min().over("stim_name", "block_index")
        ),
        num_trials_in_block=pl.col("start_time")
        .count()
        .over("stim_name", "block_index"),
    )

    line_params = {
        "color": "grey",
        "lw": 0.3,
    }
    response_window_start_time = 0.1  # np.median(np.diff(trials.select('stim_start_time', 'response_window_start_time')))
    response_window_stop_time = 1  # np.median(np.diff(trials.select('stim_start_time', 'response_window_stop_time')))
    instruction_patch_params = {
        "color": [0.88, 0.88, 0.88],
        "lw": 0,
        "zorder": -1,
    }
    add_psth = True
    nominal_rows_per_block = 20
    block_height_on_page = (
        (6 + add_psth) * nominal_rows_per_block / trials_.n_unique("block_index")
    )  # height of each row will be this value / len(block_df)
    fig, axes = plt.subplots(
        1, len(stim_names), figsize=(1.5 * len(stim_names), 6 + add_psth), sharey=True
    )
    axes = np.atleast_1d(axes)
    last_ypos: list[float] = []
    for ax, stim in zip(axes, stim_names):
        ax: plt.Axes

        stim_trials = trials_.filter(pl.col("stim_name") == stim)
        idx_in_block = 0
        for _idx, trial in enumerate(stim_trials.iter_rows(named=True)):

            num_instructed_trials = max(
                len(
                    trials.filter(  # check original trials, not modified ones with dummy instruction trials
                        pl.col("block_index") == trial["block_index"],
                        pl.col(f"is_{c}_rewarded"),
                        pl.col("is_reward_scheduled"),
                        pl.col("trial_index_in_block") < 14,
                    )
                )
                for c in ("aud", "vis")
            )

            is_vis_block: bool = "vis" in trial["rewarded_modality"]
            is_vis_target: bool = "vis1" in trial["stim_name"]
            is_aud_target: bool = "sound1" in trial["stim_name"]
            is_rewarded_stim: bool = (is_vis_target and is_vis_block) or (
                is_aud_target and not is_vis_block
            )

            if trial["is_new_block"]:
                idx_in_block = 0
                block_df = stim_trials.filter(
                    pl.col("block_index") == trial["block_index"]
                )
                ypositions = (
                    np.linspace(0, block_height_on_page, len(block_df), endpoint=False)
                    + trial["block_index"] * block_height_on_page
                )
                halfline = 0.5 * np.diff(ypositions).mean()
            ypos = ypositions[idx_in_block]

            idx_in_block += 1  # updated for next trial - don't use after this point

            if trial["is_new_block"]:
                if is_rewarded_stim:
                    assert num_instructed_trials == (
                        x := len(
                            block_df.filter(
                                (pl.col("trial_index_in_block") < 10)
                                & (pl.col("is_reward_scheduled"))
                            )
                        )
                    ), f"{x} != {num_instructed_trials=}"

                if ax is axes[0]:
                    # block label
                    rotation = 0
                    ax.text(
                        x=xlim_min - 0.6,
                        y=ypositions[0] + block_height_on_page // 2,
                        s=trial["rewarded_modality"],
                        fontsize=8,
                        ha="center",
                        va="center",
                        color=rewarded_context_colors[trial["rewarded_modality"]],
                        rotation=rotation,
                    )

                # block switch horizontal lines
                if trial["block_index"] > 0:
                    ax.axhline(
                        y=ypos - halfline,
                        **line_params,
                        zorder=99,
                    )

                if is_rewarded_stim:
                    # scheduled-reward instruction trials
                    ax.axhspan(
                        ymin=max(ypos, 0) - halfline,
                        ymax=ypositions[num_instructed_trials - 1] + halfline,
                        **instruction_patch_params,
                    )

                # if trial["is_vis_rewarded"] and len(block_df) > num_instructed_trials:
                #     # vis block grey patch
                #     ax.axhspan(
                #         ymin=(
                #             ypositions[num_instructed_trials] - halfline
                #             if is_rewarded_stim or with_instruction_trial_whitespace
                #             else ypositions[0] - halfline
                #         ),
                #         ymax=ypositions[-1] + halfline,
                #         color=[0.95] * 3,
                #         lw=0,
                #         zorder=-1,
                #     )

                # response window patch
                rect = patches.Rectangle(
                    xy=(
                        response_window_start_time,
                        (
                            y0 := (
                                ypos
                                if is_rewarded_stim
                                or not with_instruction_trial_whitespace
                                else ypositions[
                                    min(num_instructed_trials, len(block_df) - 1)
                                ]
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

            # neutral patch for instruction trials triggered after 10 consecutive misses
            if trial["is_reward_scheduled"] and trial["trial_index_in_block"] > 10:
                ax.axhspan(
                    ypos - halfline,
                    ypos + halfline,
                    **instruction_patch_params,
                )

            # spikes
            trial_spike_times = np.array(trial["stim_centered_spike_times"])
            eventplot_params = {
                "lineoffsets": ypos,
                "linewidths": 0.3,
                "linelengths": 0.8,
                "color": [0.6] * 3,
                "zorder": 99,
            }
            if trial_spike_times.size == 1 and trial_spike_times[0] is None:
                pass
            else:
                ax.eventplot(positions=trial_spike_times, **eventplot_params)

            # times of interest
            if trial["is_rewarded"]:
                time_of_interest = trial["reward_time"] - trial["stim_start_time"]
                ax.scatter(
                    [time_of_interest],
                    [ypos],
                    marker="o",
                    s=9,
                    facecolors="none",
                    edgecolors="gray",
                    linewidths=0.2,
                    zorder=100,
                )
                continue
            elif trial["is_false_alarm"]:
                if trial["response_time"] is None:
                    assert (
                        trial["task_control_response_time"] is not None
                    ), "false alarm without response time"
                    continue
                time_of_interest = trial["response_time"] - trial["stim_start_time"]
                ax.scatter(
                    [time_of_interest],
                    [ypos],
                    marker="^",
                    s=10,
                    facecolors="none",
                    edgecolors="gray",
                    linewidths=0.2,
                    zorder=100,
                )
                continue
            else:
                continue
        last_ypos.append(ypos)
    # format axes and add PSTH
    for ax, stim in zip(axes, stim_names):
        ax: plt.Axes
        if add_psth:
            average_block_psth = (
                True  # plot PSTHs for individual blocks, and their average
            )
            bin_size_s = 25 / 1000
            scale_bar_len = max(1, int(max_psth_spike_rate / 4))  # Hz
            ypad = 5
            ymin = max(last_ypos) + ypad
            ymax = ymin + nominal_rows_per_block
            ypos = ymax + 0.5

            def add_psth_plot(hist, bin_edges, **plot_kwargs):
                # need to plot upside down, scaled
                norm_spike_rate = (hist / max_psth_spike_rate) * (ymax - ymin)
                ax.plot(
                    bin_edges + np.diff(bin_edges)[0] / 2,
                    ymax - norm_spike_rate,
                    **plot_kwargs,
                )

            for rewarded_modality in ("aud", "vis"):
                color = rewarded_context_colors[rewarded_modality]

                if average_block_psth:
                    hist_results = []
                    for _, block_trials in trials.group_by("block_index"):
                        df = block_trials.filter(
                            pl.col(f"is_{rewarded_modality}_rewarded"),
                            pl.col("stim_name") == stim,
                        )
                        a = df["stim_centered_spike_times"].to_numpy()
                        if not a.size:
                            continue
                        hist, bin_edges = _make_psth(
                            spikes=np.sort(unit_spike_times),
                            start_times=np.array(df["stim_start_time"] - pad_start),
                            window_dur=pad_start + xlim_max,
                            bin_size=bin_size_s,
                        )
                        bin_edges = bin_edges - pad_start
                        # hist, bin_edges = hist_(a)
                        hist_results.append(hist)
                        add_psth_plot(hist, bin_edges, lw=0.3, c=color, alpha=0.3)
                    if not hist_results:
                        continue
                    add_psth_plot(
                        np.mean(hist_results, axis=0), bin_edges, lw=0.75, c=color
                    )
                else:
                    df = trials.filter(
                        pl.col(f"is_{rewarded_modality}_rewarded"),
                        pl.col("stim_name") == stim,
                    )
                    hist, bin_edges = _make_psth(
                        spikes=np.sort(unit_spike_times),
                        start_times=np.array(df["stim_start_time"] - pad_start),
                        window_dur=pad_start + xlim_max,
                        bin_size=bin_size_s,
                    )
                    bin_edges = bin_edges - pad_start
                    add_psth_plot(hist, bin_edges, lw=0.5, c=color)

            # response window patch in PSTH
            rect = patches.Rectangle(
                xy=(response_window_start_time, ymin),
                width=response_window_stop_time - response_window_start_time,
                height=ymax - ymin + 0.5,
                linewidth=0,
                edgecolor="none",
                facecolor=[0.9, 0.9, 0.9, 0.5],
                zorder=-1,
            )
            ax.add_patch(rect)
            if ax is axes[0]:
                # add a scale bar
                length = (ymax - ymin) * scale_bar_len / max_psth_spike_rate
                ax.plot(
                    [xlim_min - 0.1, xlim_min - 0.1],
                    [ymax - length, ymax],
                    c="k",
                    lw=1,
                    clip_on=False,
                )
                ax.text(
                    x=xlim_min - 0.6,
                    y=ymax - (length / 2),
                    s=f"{scale_bar_len} Hz",
                    fontsize=6,
                    ha="center",
                    va="center",
                    color="k",
                    rotation=0,
                )

        # stim onset vertical line
        ax.axvline(x=0, **line_params)

        ax.set_xlim(xlim_min, xlim_max)
        ax.set_ylim(-0.5, max(ypos, *last_ypos) + 0.5)
        ax.set_xticks(sorted({min(xlim_min, 0), 0, xlim_max}))
        # ax.set_xticklabels("" if v % 2 else str(v) for v in ax.get_xticks())
        ax.xaxis.set_tick_params(labelsize=6)
        ax.set_yticks([])
        if ax is axes[0]:
            ax.set_ylabel("<- Trials")
            ax.yaxis.set_label_coords(x=-0.5, y=0.5)
            ax.text(
                x=xlim_min - 0.9,
                y=-0,
                s="Rewarded\nmodality",
                fontsize=8,
                ha="center",
                va="center",
                color="k",
                rotation=0,
            )
        ax.set_xlabel("time from\nstimulus onset (s)")
        ax.invert_yaxis()
        ax.set_aspect(0.1 * (xlim_max - xlim_min) / 3)
        stim_to_label = {
            "vis1": "vis target",
            "vis2": "vis non-target",
            "sound1": "aud target",
            "sound2": "aud non-target",
        }
        ax.set_title(stim_to_label[stim], fontsize=8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.set_zorder(199)


    if unit.is_empty():
        location = "not in units df"
    else:
        if "location" in unit.columns:
            location = unit["location"][0]
        else:
            location = "no CCF location (unannotated)"
    fig.set_dpi(300)
    fig.suptitle(f"{unit_id = !r} | {location = !r}", fontsize=10)
    if show_event_marker_legend:
        legend_handles = [
            Line2D(
                [],
                [],
                marker="o",
                linestyle="none",
                markerfacecolor="none",
                markeredgecolor="gray",
                markeredgewidth=0.5,
                markersize=4,
                label="hit",
            ),
            Line2D(
                [],
                [],
                marker="^",
                linestyle="none",
                markerfacecolor="none",
                markeredgecolor="gray",
                markeredgewidth=0.5,
                markersize=4,
                label="false alarm",
            ),
        ]
        fig.legend(
            handles=legend_handles,
            loc="upper right",
            bbox_to_anchor=(0.99, 0.985),
            frameon=False,
            fontsize=7,
            handletextpad=0.4,
            borderaxespad=0,
            labelspacing=0.25,
        )
    return fig


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("unit_id", nargs="?", default=nwb_access.SPECIFIC_UNIT_IDS[0])
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()

    fig = plot(unit_id=args.unit_id, stim_names=("sound1", "vis1", "sound2", "vis2"))
    output = args.output or pathlib.Path(f"unit_raster_psth_plot_{args.unit_id}.png")
    fig.savefig(output, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(output)

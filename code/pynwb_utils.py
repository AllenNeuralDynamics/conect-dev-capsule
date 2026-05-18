from __future__ import annotations

import pandas as pd
import altair as alt

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

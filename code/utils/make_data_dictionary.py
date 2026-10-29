"""Write a data dictionary for one Dynamic Routing NWB file.

For every table, column and timeseries in the file, the dictionary lists:
how to access it with pynwb, its NWB type, dtype, shape, unit, value range
(or the most common values, for text) and the description stored in the file.

Usage (from a terminal or a notebook cell):

    Terminal: 
    python make_data_dictionary.py /root/capsule/data/dynamicrouting_datacube/<session folder>/<session>.nwb.zarr

    Notebook cell: 
    from make_data_dictionary import write_dictionary

    data_dict = write_dictionary(nwb_path, out_dir="/root/capsule/results")
    data_dict.head()    

Writes two files next to where it is run:
    <session>_data_dictionary.md   readable version, one section per table / timeseries
    <session>_data_dictionary.csv  one row per field, for filtering and sorting
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd
import pynwb
from hdmf.common import DynamicTable, VectorIndex

MAX_VALUES_TO_SCAN = 2_000_000   # larger arrays are summarized from their first rows only
N_COMMON_VALUES = 6            # how many common values to list for text columns
SKIP_COLUMNS = {"electrode_group", "group"}   # object references (stored pickled); use the *_name columns instead


# --------------------------------------------------------------------------------------
# Walking the file
# --------------------------------------------------------------------------------------

def iter_objects(nwb):
    """Yield (pynwb access expression, section, object) for everything worth describing."""
    if nwb.subject is not None:
        yield "nwb.subject", "general", nwb.subject
    for name, obj in nwb.devices.items():
        yield f'nwb.devices["{name}"]', "general", obj
    for name, obj in nwb.electrode_groups.items():
        yield f'nwb.electrode_groups["{name}"]', "general", obj
    if nwb.electrodes is not None:
        yield "nwb.electrodes", "general", nwb.electrodes
    for name, obj in nwb.acquisition.items():
        yield f'nwb.acquisition["{name}"]', "acquisition", obj
    for name, obj in nwb.intervals.items():
        yield f'nwb.intervals["{name}"]', "intervals", obj
    for module_name, module in nwb.processing.items():
        for name, obj in module.data_interfaces.items():
            yield f'nwb.processing["{module_name}"]["{name}"]', f"processing/{module_name}", obj
    for name, obj in nwb.analysis.items():
        yield f'nwb.analysis["{name}"]', "analysis", obj
    if nwb.units is not None:
        yield "nwb.units", "units", nwb.units


# --------------------------------------------------------------------------------------
# Summarizing values
# --------------------------------------------------------------------------------------

def read_values(data):
    """Load an array, or only its first rows if it is very large. Returns (numpy array, note)."""
    shape = getattr(data, "shape", (len(data),))
    values_per_row = int(np.prod(shape[1:])) if len(shape) > 1 else 1
    max_rows = max(1, MAX_VALUES_TO_SCAN // values_per_row)
    if shape[0] > max_rows:
        return np.asarray(data[:max_rows]), f"first {max_rows:,} rows"
    return np.asarray(data[:]), ""


def summarize_values(values: np.ndarray) -> str:
    """One short, human-readable line describing the values in an array."""
    if values.size == 0:
        return "empty"
    if values.dtype == bool:
        n_true = int(values.sum())
        return f"True: {n_true:,} / False: {values.size - n_true:,}"
    if np.issubdtype(values.dtype, np.number):
        finite = values[np.isfinite(values)] if np.issubdtype(values.dtype, np.floating) else values
        n_nan = values.size - finite.size
        text = "all NaN" if finite.size == 0 else f"{_fmt(finite.min())} to {_fmt(finite.max())}"
        return text + (f" ({n_nan:,} NaN)" if n_nan else "")
    # text and other objects
    flat = pd.Series(values.ravel()).map(lambda v: v.decode() if isinstance(v, bytes) else v).astype(str)
    counts = flat.value_counts()
    if len(counts) == flat.size and flat.size > N_COMMON_VALUES:
        return f"{flat.size:,} unique values, e.g. " + ", ".join(repr(v) for v in flat.head(3))
    common = ", ".join(f"{v!r} ({n:,})" for v, n in counts.head(N_COMMON_VALUES).items())
    more = f", ... {len(counts):,} unique" if len(counts) > N_COMMON_VALUES else ""
    return common + more


def _fmt(x) -> str:
    x = float(x)
    if not np.isfinite(x):
        return str(x)                     # nan, inf, -inf
    if x == int(x) and abs(x) < 1e12:
        return f"{int(x):,}"
    return f"{x:.4g}"


def dtype_name(values: np.ndarray) -> str:
    if values.dtype == object:
        return "str" if values.size and isinstance(values.flat[0], (str, bytes)) else "object"
    return str(values.dtype)


# --------------------------------------------------------------------------------------
# Describing each kind of object
# --------------------------------------------------------------------------------------

def describe_table(table: DynamicTable) -> list[dict]:
    rows = []
    for column in table.columns:
        if isinstance(column, VectorIndex):
            continue                      # described together with the column it indexes
        name = column.name
        row = {"field": name, "description": column.description or "", "unit": ""}
        if name in SKIP_COLUMNS:
            rows.append({**row, "dtype": "object reference", "shape": f"({len(table):,},)",
                         "values": "not read (object reference); see the matching *_name column"})
            continue
        try:
            is_ragged = isinstance(table[name], VectorIndex)
            values, note = read_values(column.data)
            if is_ragged:
                index = np.asarray(table[name].data[:])
                lengths = np.diff(np.concatenate([[0], index]))
                shape = f"({len(table):,} rows, ragged: {_fmt(lengths.min())} to {_fmt(lengths.max())} values per row)"
            else:
                shape = str(tuple(column.data.shape)) if hasattr(column.data, "shape") else f"({len(values):,},)"
            summary = summarize_values(values) + (f" [{note}]" if note else "")
            rows.append({**row, "dtype": dtype_name(values), "shape": shape, "values": summary})
        except Exception as error:      # e.g. a codec that refuses to decode
            rows.append({**row, "dtype": "?", "shape": "?", "values": f"could not read: {type(error).__name__}"})
    return rows


def describe_timeseries(ts) -> list[dict]:
    rows = []
    values, note = read_values(ts.data)
    rows.append({
        "field": "data",
        "description": ts.description or "",
        "unit": getattr(ts, "unit", "") or "",
        "dtype": dtype_name(values),
        "shape": str(tuple(ts.data.shape)),
        "values": summarize_values(values) + (f" [{note}]" if note else ""),
    })
    if ts.timestamps is not None:
        times = np.asarray(ts.timestamps[:], dtype=float)
        rate = 1 / np.nanmedian(np.diff(times)) if len(times) > 1 else np.nan
        rows.append({
            "field": "timestamps",
            "description": "sample times",
            "unit": "seconds",
            "dtype": dtype_name(times),
            "shape": str(times.shape),
            "values": summarize_values(times) + (f" (~{rate:.4g} Hz)" if np.isfinite(rate) else ""),
        })
    elif ts.rate is not None:
        rows.append({"field": "rate", "description": "sampling rate", "unit": "Hz", "dtype": "float",
                     "shape": "", "values": f"{ts.rate:g} (starting at {ts.starting_time:g} s)"})
    return rows


def describe_fields(obj) -> list[dict]:
    """Simple containers (Subject, Device, ElectrodeGroup): list their scalar fields."""
    rows = []
    for name, value in obj.fields.items():
        if hasattr(value, "fields") or name in {"device"}:
            value = getattr(value, "name", value)
        rows.append({"field": name, "description": "", "unit": "", "dtype": type(value).__name__,
                     "shape": "", "values": str(value)})
    return rows


def describe(obj) -> list[dict]:
    if isinstance(obj, DynamicTable):
        return describe_table(obj)
    if isinstance(obj, pynwb.base.TimeSeries):
        return describe_timeseries(obj)
    return describe_fields(obj)


def n_rows(obj) -> str:
    if isinstance(obj, DynamicTable):
        return f"{len(obj):,} rows"
    if isinstance(obj, pynwb.base.TimeSeries):
        return f"{len(obj.data):,} samples"
    return ""


# --------------------------------------------------------------------------------------
# Writing the output
# --------------------------------------------------------------------------------------

def _md_cell(text) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def write_dictionary(nwb_path: str | pathlib.Path, out_dir: str | pathlib.Path = ".") -> pd.DataFrame:
    nwb = pynwb.read_nwb(nwb_path)
    session = nwb.session_id or pathlib.Path(nwb_path).name.split(".")[0]

    records = []
    md = [
        f"# Data dictionary: {session}",
        "",
        f"Generated from `{pathlib.Path(nwb_path).name}` with `make_data_dictionary.py`.",
        "Times are in seconds relative to `nwb.session_start_time`. "
        f"Value ranges for arrays with more than {MAX_VALUES_TO_SCAN:,} values are computed from their first rows only "
        "(marked in the table).",
        "",
        "## Session metadata",
        "",
        "| field | value |",
        "|---|---|",
    ]
    for field in ["session_id", "session_description", "session_start_time", "institution", "lab",
                  "experimenter", "keywords", "experiment_description"]:
        value = getattr(nwb, field, None)
        if value is not None:
            if hasattr(value, "shape") and not isinstance(value, str):   # e.g. a lazily-loaded array
                value = np.asarray(value[:]).tolist()
            if isinstance(value, (list, tuple, np.ndarray)):
                value = ", ".join(map(str, value))
            md.append(f"| `{field}` | {_md_cell(value)} |")

    section = None
    for access, obj_section, obj in iter_objects(nwb):
        if obj_section != section:
            section = obj_section
            md += ["", f"## {section}"]
        print(f"  {access}", file=sys.stderr)
        try:
            rows = describe(obj)
        except Exception as error:      # keep going: report the problem in the dictionary instead
            print(f"    could not describe: {type(error).__name__}: {error}", file=sys.stderr)
            rows = [{"field": "?", "description": "", "unit": "", "dtype": "?", "shape": "?",
                     "values": f"could not read: {type(error).__name__}"}]
        type_name = type(obj).__name__
        md += ["", f"### `{access}`", "",
               f"**{type_name}** {('· ' + n_rows(obj)) if n_rows(obj) else ''}"]
        description = getattr(obj, "description", None)
        if description:
            md += ["", f"> {_md_cell(description)}"]
        md += ["", "| field | dtype | shape | unit | values | description |", "|---|---|---|---|---|---|"]
        for row in rows:
            md.append("| " + " | ".join(_md_cell(row[k]) if k != "field" else f"`{row[k]}`"
                                        for k in ["field", "dtype", "shape", "unit", "values", "description"]) + " |")
            records.append({"section": section, "object": access, "neurodata_type": type_name, **row})

    out_dir = pathlib.Path(out_dir)
    (out_dir / f"{session}_data_dictionary.md").write_text("\n".join(md) + "\n")
    table = pd.DataFrame(records)
    table.to_csv(out_dir / f"{session}_data_dictionary.csv", index=False)
    print(f"wrote {session}_data_dictionary.md and .csv to {out_dir.resolve()}", file=sys.stderr)
    return table


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    write_dictionary(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ".")
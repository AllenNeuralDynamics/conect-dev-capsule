from __future__ import annotations

import json
import os
import pathlib
from collections.abc import Iterable
from typing import Any

import lazynwb
from lazynwb.table_metadata import get_table_column_metadata


ASSETS_HDF5_JSON = pathlib.Path(__file__).with_name("assets_hdf5.json")
ASSETS_ZARR_JSON = pathlib.Path(__file__).with_name("assets_zarr.json")
DEFAULT_CAPSULE_DATA_DIR = pathlib.Path(
    os.environ.get("CAPSULE_DATA_DIR", "/root/capsule/data")
)

SPECIFIC_UNIT_IDS = [
    "713655_2024-08-09_C-630",
    "713655_2024-08-09_E-235",
    "713655_2024-08-09_E-167",
]


def assets_json_path(zarr: bool = True) -> pathlib.Path:
    return ASSETS_ZARR_JSON if zarr else ASSETS_HDF5_JSON


def session_id_from_unit_id(unit_id: str) -> str:
    parts = unit_id.split("_")
    if len(parts) < 3:
        raise ValueError(
            f"Expected unit_id like '713655_2024-08-09_C-630', got {unit_id!r}"
        )
    return "_".join(parts[:2])


def _coerce_nwb_paths(
    nwb_paths: Iterable[str | pathlib.Path] | str | pathlib.Path,
) -> tuple[str, ...]:
    if isinstance(nwb_paths, str | pathlib.Path):
        return (str(nwb_paths),)
    return tuple(str(path) for path in nwb_paths)


def load_assets(
    assets_json: str | pathlib.Path | None = None,
    *,
    zarr: bool = True,
) -> tuple[dict[str, Any], ...]:
    assets_json = assets_json or assets_json_path(zarr)
    return tuple(json.loads(pathlib.Path(assets_json).read_text()))


def get_nwb_paths(
    assets_json: str | pathlib.Path | None = None,
    data_dir: str | pathlib.Path = DEFAULT_CAPSULE_DATA_DIR,
    prefer_local: bool = True,
    *,
    zarr: bool = True,
) -> tuple[str, ...]:
    paths: list[str] = []
    data_dir = pathlib.Path(data_dir)
    for asset in load_assets(assets_json, zarr=zarr):
        nwb_name = pathlib.PurePosixPath(asset["nwb_path"]).name
        local_path = data_dir / asset["mount"] / nwb_name
        if prefer_local and local_path.exists():
            paths.append(str(local_path))
        else:
            paths.append(asset["nwb_path"])
    return tuple(paths)


def get_session_nwb_path(
    session_id: str,
    nwb_paths: Iterable[str | pathlib.Path] | str | pathlib.Path | None = None,
    *,
    zarr: bool = True,
    assets_json: str | pathlib.Path | None = None,
    data_dir: str | pathlib.Path = DEFAULT_CAPSULE_DATA_DIR,
    prefer_local: bool = True,
) -> str:
    if nwb_paths is None:
        paths = get_nwb_paths(
            assets_json=assets_json,
            data_dir=data_dir,
            prefer_local=prefer_local,
            zarr=zarr,
        )
    else:
        paths = _coerce_nwb_paths(nwb_paths)
    matches = tuple(path for path in paths if session_id in path)
    if not matches:
        raise ValueError(f"No NWB path found for session {session_id!r}")
    if len(matches) > 1:
        raise ValueError(f"Multiple NWB paths found for session {session_id!r}")
    return matches[0]


def get_unit_nwb_path(
    unit_id: str,
    nwb_paths: Iterable[str | pathlib.Path] | str | pathlib.Path | None = None,
    *,
    zarr: bool = True,
    assets_json: str | pathlib.Path | None = None,
    data_dir: str | pathlib.Path = DEFAULT_CAPSULE_DATA_DIR,
    prefer_local: bool = True,
) -> str:
    return get_session_nwb_path(
        session_id_from_unit_id(unit_id),
        nwb_paths=nwb_paths,
        zarr=zarr,
        assets_json=assets_json,
        data_dir=data_dir,
        prefer_local=prefer_local,
    )


def get_nwb_sources(
    nwb_paths: Iterable[str | pathlib.Path] | str | pathlib.Path | None = None,
    *,
    session_id: str | None = None,
    unit_id: str | None = None,
    zarr: bool = True,
    assets_json: str | pathlib.Path | None = None,
    data_dir: str | pathlib.Path = DEFAULT_CAPSULE_DATA_DIR,
    prefer_local: bool = True,
) -> tuple[str, ...]:
    if unit_id is not None:
        unit_session_id = session_id_from_unit_id(unit_id)
        if session_id is not None and session_id != unit_session_id:
            raise ValueError(
                f"unit_id {unit_id!r} belongs to session {unit_session_id!r}, "
                f"not {session_id!r}"
            )
        session_id = unit_session_id

    if nwb_paths is None:
        paths = get_nwb_paths(
            assets_json=assets_json,
            data_dir=data_dir,
            prefer_local=prefer_local,
            zarr=zarr,
        )
    else:
        paths = _coerce_nwb_paths(nwb_paths)

    if session_id is None:
        return paths
    return (
        get_session_nwb_path(
            session_id,
            nwb_paths=paths,
            zarr=zarr,
            assets_json=assets_json,
            data_dir=data_dir,
            prefer_local=prefer_local,
        ),
    )


def scan_table(
    table_path: str,
    nwb_paths: Iterable[str | pathlib.Path] | str | pathlib.Path | None = None,
    *,
    session_id: str | None = None,
    unit_id: str | None = None,
    zarr: bool = True,
    assets_json: str | pathlib.Path | None = None,
    data_dir: str | pathlib.Path = DEFAULT_CAPSULE_DATA_DIR,
    prefer_local: bool = True,
    **scan_kwargs: Any,
):
    scan_kwargs.setdefault("disable_progress", True)
    return lazynwb.scan_nwb(
        source=get_nwb_sources(
            nwb_paths=nwb_paths,
            session_id=session_id,
            unit_id=unit_id,
            zarr=zarr,
            assets_json=assets_json,
            data_dir=data_dir,
            prefer_local=prefer_local,
        ),
        table_path=table_path,
        **scan_kwargs,
    )


def get_table_column_descriptions(
    table_path: str,
    nwb_paths: Iterable[str | pathlib.Path] | str | pathlib.Path | None = None,
    *,
    session_id: str | None = None,
    unit_id: str | None = None,
    zarr: bool = True,
    assets_json: str | pathlib.Path | None = None,
    data_dir: str | pathlib.Path = DEFAULT_CAPSULE_DATA_DIR,
    prefer_local: bool = True,
    columns: Iterable[str] | None = None,
) -> dict[str, str]:
    """Return NWB column descriptions for a table without reading table data."""
    sources = get_nwb_sources(
        nwb_paths=nwb_paths,
        session_id=session_id,
        unit_id=unit_id,
        zarr=zarr,
        assets_json=assets_json,
        data_dir=data_dir,
        prefer_local=prefer_local,
    )
    if not sources:
        raise ValueError("No NWB sources available for table metadata lookup")

    metadata = get_table_column_metadata(sources[0], table_path)
    descriptions = {
        column.name: description
        for column in metadata
        if (description := column.attrs.get("description"))
    }

    if columns is None:
        return descriptions

    return {
        column_name: descriptions[column_name]
        for column_name in columns
        if column_name in descriptions
    }

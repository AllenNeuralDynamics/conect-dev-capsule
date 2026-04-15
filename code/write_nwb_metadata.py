import pathlib

import lazynwb
import polars as pl

def write_nwb_metadata() -> None:
    nwb_paths = list(pathlib.Path("/root/capsule/data").glob("*/*.nwb"))
    (
        lazynwb.get_metadata_df(nwb_paths, as_polars=True)
        .drop('keywords') # list not supported in csv
        .drop(pl.selectors.by_dtype(pl.Null)) # drop any columns that are all null values
        .write_csv("/root/capsule/results/metadata.csv")
    )

if __name__ == "__main__":
    write_nwb_metadata()
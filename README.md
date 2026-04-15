# conect-dev-capsule

Each attached asset contains:
- an .nwb file (.hdf5)
- `nwb_contents.json` detailing the internal paths within each .hdf5 file, e.g.:
    ```
    [
        "/intervals/trials",
        "/processing/behavior/running_speed",
        "/units"
    ]   
    ```

- AIND metadata files
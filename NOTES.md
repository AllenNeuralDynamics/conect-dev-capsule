- started because of frustration with the units table:
    - size of data can be large due to array columns (waveform_mean, waveform_sd) and ragged arrays (spike_times, spike_amplitudes)
    - eagerly loading all data in the table is extremely inefficient when streaming from S3
    
- inspired by polars scan_parquet and lazy evaluation
    - instead of `read_parquet()`, which eagerly loads all data and returns a DataFrame, `scan_parquet()` returns a LazyFrame, which is essentially some metadata and a query plan describing how it *will* load data when `.collect()` is called on it 
    - parquet stores table schema in the file, so the schema is available with a single request 
    - scan_parquet can query a single file or multiple files (if they have compatible schema)
        - NWB ISSUE: getting schema is involved, due to custom implementations of ragged arrays etc in HDMF. Inefficient as it requires many requests to query dtypes or sample data (although can be parallelized). Scales with number of files.
    - can filter rows based on any column or expression
    - expressions are composable, can reference other columns, can be inspected, can be serialized to JSON - stateless and contain no reference to any dataframe or underlying data
        example: 
            (pl.col('response_time') - pl.col('stim_start_time')) < 0.1


    - polars ensures expressions are compatible with the schema: try filtering with a column that doesn't exist and polars will raise:
        lf.filter(fast_responses)
    - can additionally select subset of columns to materialize (any columns not involved in query will not be loaded)
    - can collect_schema after applying filter
    - the way parquet stores data can also facilitate this lazy scan-filter-select-collect pattern - the data in each column is chunked into "row groups" that are compressed individually. some stats are stored for each chunk, like min/max/distinct count/null count, so the query planner can check which chunks match the row filter and skip the others
        https://data-mozart.com/wp-content/uploads/2023/04/Row-groups.png
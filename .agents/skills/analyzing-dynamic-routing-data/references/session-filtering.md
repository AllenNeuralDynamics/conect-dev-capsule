# Session filtering criteria

Although all released data is "production" quality in terms of how it was collected, sessions with
below-par behavioral performance are still included. The released dataset may also include sessions with
optogenetic or pharmacological manipulations, sessions without a context switch ("Templeton") that
can act as a control, and experiments with subjects that had not previously been exposed to the
context-switching task.

Apply the correct filters for the analysis instead of assuming all released sessions are comparable.

## "Standard" brain-wide survey ephys sessions

Use the following `keywords` filter to select sessions that included the standard `DynamicRouting1`
context-switching task and did not include manipulations:

```python
pl.Expr.and_(
    *[
        pl.col("keywords").list.contains("production"),
        ~pl.col("keywords").list.contains("issues"),
        pl.col("keywords").list.contains("task"),
        pl.col("keywords").list.contains("ephys"),
        pl.col("keywords").list.contains("ccf"),
        ~pl.col("keywords").list.contains("opto_perturbation"),
        ~pl.col("keywords").list.contains("opto_control"),
        ~pl.col("keywords").list.contains("injection_perturbation"),
        ~pl.col("keywords").list.contains("injection_control"),
        ~pl.col("keywords").list.contains("hab"),
        ~pl.col("keywords").list.contains("training"),
        ~pl.col("keywords").list.contains("context_naive"),
        ~pl.col("keywords").list.contains("templeton"),
    ]
)
```
Sanity checks: 
- `is_opto` in the trials table should never be True

## Behavioral performance criteria for "good" sessions

For context-switching analyses, require that the subject was engaged and showed good task
performance for most of the session.

For ephys sessions, use:
- at least 2 blocks for each rewarded modality with:
- `cross_modal_dprime >= 1.0`
- at least 10 trials
- at least 10 contingent rewards

For behavior sessions, use:
- at least 4 blocks of either rewarded modality with:
- at least 10 trials
- at least 10 contingent rewards

## Example implementation

```python
def passing_blocks_performance_filter(
    min_cross_modality_dprime: float | None = 1.0,
    min_trials: int | None = 10,
    min_contingent_rewards: int | None = 10,
) -> pl.Expr:
    """Filter `/intervals/performance` rows to passing blocks."""
    cross_modal_dprime_filter: pl.Expr = (
        pl.col("cross_modality_dprime") >= min_cross_modality_dprime
        if min_cross_modality_dprime is not None
        else pl.lit(True)
    )
    min_n_trials_filter: pl.Expr = (
        pl.col("n_trials") >= min_trials if min_trials is not None else pl.lit(True)
    )
    min_n_responses_filter: pl.Expr = (
        pl.col("n_responses") >= min_contingent_rewards
        if min_contingent_rewards is not None
        else pl.lit(True)
    )
    return (
        cross_modal_dprime_filter
        & min_n_trials_filter
        & min_n_responses_filter
    )


def get_passing_session_ids(
    min_cross_modality_dprime: float | None = 1.0,
    min_trials: int | None = 10,
    min_contingent_rewards: int | None = 10,
    of_each_rewarded_modality: bool = True,
    min_n_blocks: int = 2,
    include_templeton: bool = False,
) -> pl.Series:
    passing_block_filter = passing_blocks_performance_filter(
        min_cross_modality_dprime=min_cross_modality_dprime,
        min_trials=min_trials,
        min_contingent_rewards=min_contingent_rewards,
    )
    n_blocks_each_context: pl.Expr = (
        pl.col("rewarded_modality")
        .filter(passing_block_filter)
        .unique_counts()
        .over("session_id", mapping_strategy="join")
    )
    if include_templeton:
        templeton_session_ids = get_session_table().filter("is_templeton")["session_id"]
        templeton_filter = pl.col("session_id").is_in(templeton_session_ids)
    else:
        templeton_filter = pl.lit(False)
    if of_each_rewarded_modality:
        passing_session_filter = (
            (
                n_blocks_each_context.list.eval(pl.element() >= min_n_blocks).list.all()
                & (n_blocks_each_context.list.len() == 2)
            )
            | templeton_filter
        )
    else:
        passing_session_filter = (
            (n_blocks_each_context.list.sum() >= min_n_blocks) | templeton_filter
        )
    return (
        get_df("performance")
        .filter(passing_session_filter.explode())["session_id"]
        .unique()
        .sort()
    )
```
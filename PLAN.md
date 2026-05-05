# Dynamic Routing Tutorial Notebook

## Summary
Build `code/dynamic_routing_tutorial.ipynb`: worked narrative tutorial for trainee neuroscientists using `713655_2024-08-09` as the main session and `713655_2024-08-09_E-167` as the main neural example.

Use `lazynwb` for runnable cells. Show PyNWB/Zarr loading only as a markdown reference snippet. The notebook should teach data access, task design, real behavior, one neural example, and one running-speed covariate check.

## Key Changes
- Add thin helper in `code/nwb_access.py` for NWB table column descriptions from `lazynwb.table_metadata`.
- Keep analysis logic visible in notebook cells: trials, block summaries, timing, performance, running speed, and response rates.
- Use `code/unit_raster_psth_plot.py` for raster/PSTH, adding only small optional styling parameters if needed.
- Use E-167 as the main neural example: CP unit, `is_qc_pass=True`, `is_not_drift=True`, `activity_drift=0.0516`.
- Use minimal generic plot formatting. Use Allen colors only for rewarded context: visual-rewarded `#6464FF`, auditory-rewarded `#CD0F55`.
- Encode stimulus identity and outcomes with labels, panel titles, rows, and hollow marker shapes rather than color.
- Display plots inline only; do not save plot files to `results/`.
- No session class.
- Use current deps: `matplotlib`, `numpy`, `polars`, `lazynwb`.

## Notebook Flow
- Dataset/session intro from `README.md`.
- Zarr asset discovery and `lazynwb.scan_table` access patterns.
- Non-executed PyNWB/Zarr snippet using `NWBZarrIO`.
- Selected `/intervals/trials` column-description dict.
- Block summary plot: six blocks with rewarded modality, trial counts, and instruction/auto-reward placement or counts.
- Update block summary plot with block 0 at the top, light-green instruction-trial spans, and black tick marks for actual non-contingent rewards.
- Match instruction span and non-contingent reward tick height to the regular trial context bars, and move the block-structure legend to a horizontal strip above the axes.
- Aggregate timing plot: mean quiescent, stimulus, and response-window timing from `/intervals/trials`; overlay hit and false-alarm response times for visual/auditory stimuli only, excluding catch. Use hollow circle/triangle marker shapes by stimulus modality.
- Target-only behavior plot: compute response rates from `/intervals/trials`, excluding instruction/auto-reward trials; plot `vis1` and `sound1` response rates across block index; show `/intervals/performance` as a richer comparison table.
- Add a rewarded-modality color legend to the target-only behavior plot.
- E-167 unit metadata plus four-stimulus raster/PSTH for `vis1`, `sound1`, `vis2`, and `sound2`.
- Add a subtle legend to the raster/PSTH for hollow hit and false-alarm markers.
- Trial-aligned running-speed plot: align to stimulus onset for visual and auditory targets split by rewarded context; show mean plus SEM band.
- Update running-speed plot to split target trials into correct and incorrect outcome rows: top row overlays hit and correct-reject trials; bottom row overlays false-alarm and miss trials, preserving target identity columns and rewarded-context colors.
- Clean up the aggregate timing plot by labeling the mean quiescent, stimulus, and response-window patches above the plot with pointer annotations, and move the hollow marker legend outside the axes as a horizontal legend at the top.
- Add a pupil-area covariate check from `/processing/behavior/eye_tracking`, using `pupil_area` and excluding `pupil_is_bad_frame`, with the same correct/incorrect outcome-row layout as the running-speed plot.
- Closing caveats and interpretation prompts.

## Test Plan
- Test column-description helper on selected trial columns.
- Execute notebook top-to-bottom.
- Manually inspect inline plots for the agreed encodings and instruction-trial handling.
- Confirm spike access stays predicate/projection-based and does not load all unit spike arrays.
- Do not add new automated plot tests.

## Assumptions
- Audience knows basic Python, not NWB/lazynwb/Dynamic Routing.
- The tutorial is for teaching data access plus interpretation, not publication-ready figure generation.
- Timing response dots exclude catch trials so every dot has a visual or auditory stimulus modality.
- Outcome encoding uses shape/position only; no hit/false-alarm colors.

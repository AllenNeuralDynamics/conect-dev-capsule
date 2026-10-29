# Dynamic Routing NWB files: a guide to what's inside

Each session of the Dynamic Routing project is packaged as **one NWB file** (Zarr format, `<subject>_<date>.nwb.zarr`).
It contains the task trials, spike-sorted units, probe and electrode metadata, and processed behavior
(running, licks, rewards, face and eye tracking).

This guide shows how the file is organized, how to reach each part with `pynwb`, and the conventions shared
across fields. For a description of the experiment (task, trials, etc), see the [README](README.md#task).
For every column's dtype, shape and value range, see the [data dictionary](#full-data-dictionary).

---

## Quick start

```python
import pynwb

nwb = pynwb.read_nwb("/root/capsule/data/dynamicrouting_datacube/<session folder>/<session>.nwb.zarr")

nwb.intervals.keys()                        # interval tables: trials, epochs, ...
nwb.processing["behavior"].data_interfaces  # processed behavior
nwb.units.colnames                          # columns of the units table

trials = nwb.trials[:]                      # any table -> pandas DataFrame
nwb.trials["stim_name"].description         # description of one column
```
---

## Conventions

| Convention | Definition |
|---|---|
| **Times** | Seconds, relative to `nwb.session_start_time`. Every `*_time` column and every `timestamps` array uses the same clock, so they can be compared directly. |
| **`*_time` columns** | Event times within a trial or interval, e.g. `stim_start_time`, `response_time`. `NaN` means the event didn't happen (e.g. no lick). |
| **`is_*` columns** | Booleans for filtering rows, e.g. `trials.query("is_hit")`. |
| **`*_index` columns** | 0-indexed integers, e.g. `block_index`, `trial_index_in_block`. |
| **Tables** | Stored as `DynamicTable`s. `table[:]` or `table.to_dataframe()` returns a DataFrame; `table.colnames` lists columns; `table[col].description` explains each one. |
| **Ragged columns** | Some columns hold a variable-length list per row (e.g. `units.spike_times`, `epochs.interval_names`). In a DataFrame each cell is an array. |
| **Timeseries** | `TimeSeries` objects have `.data`, `.timestamps` and `.unit`. Load them with `.data[:]` (or a slice, for large arrays). |
| **Brain coordinates** | Allen CCF v3, in µm: `ccf_ap` / `x` (+ is posterior), `ccf_dv` / `y` (+ is inferior), `ccf_ml` / `z` (+ is right). `structure` is the coarse area acronym, `location` the more specific CCF acronym. |
| **Video coordinates** | Pixels, with (0, 0) at the top-left of the frame, so +y is *down*. |

---

## File Structure

```
NWBFile
├── session metadata        nwb.session_id, nwb.session_start_time, nwb.institution, ...
├── general
│   ├── subject             nwb.subject                       Subject (age, sex, genotype, strain, ...)
│   ├── devices             nwb.devices                       Neuropixels probes and their manipulators
│   ├── electrode groups    nwb.electrode_groups              one per probe (probeA, probeB, ...)
│   └── electrodes          nwb.electrodes                    one row per recording channel
├── intervals
│   ├── epochs              nwb.intervals["epochs"]           phases of the session
│   ├── trials              nwb.trials                        task trials, one row per trial
│   ├── performance         nwb.intervals["performance"]      behavior summary, one row per block
│   ├── vis_rf_mapping_trials   nwb.intervals["vis_rf_mapping_trials"]
│   ├── aud_rf_mapping_trials   nwb.intervals["aud_rf_mapping_trials"]
│   └── optotagging_trials  nwb.intervals["optotagging_trials"]
├── units                   nwb.units                         spike-sorted units, one row per unit
├── processing
│   ├── behavior            nwb.processing["behavior"][...]
│   │   ├── running_speed                   TimeSeries
│   │   ├── licks                           DynamicTable   one row per lick-spout contact
│   │   ├── rewards                         DynamicTable   one row per reward
│   │   ├── quiescent_interval_violations   DynamicTable
│   │   ├── lp_side_camera, lp_front_camera DynamicTable   face keypoints, one row per video frame
│   │   ├── dlc_eye_camera                  DynamicTable   eye keypoints, one row per video frame
│   │   ├── eye_tracking                    DynamicTable   pupil / eyelid / corneal-reflection ellipses
│   │   └── facemap_side_camera, facemap_front_camera   TimeSeries   motion SVD (frames x 500)
│   └── ecephys             (empty)
├── acquisition
│   ├── frametimes_eye_camera, frametimes_front_camera, frametimes_side_camera   DynamicTable
│   └── manipulator_positions                                                    DynamicTable
├── stimulus                (empty)
└── analysis                (empty)
```
---

## Sections

### Session metadata and `general`

| Access | Definition |
|---|---|
| `nwb.session_id`, `nwb.session_start_time`, `nwb.experimenter`, `nwb.keywords`, ... | Session-level metadata. `session_start_time` is the zero point for all times in the file. |
| `nwb.subject` | Subject info: `subject_id`, `age`, `date_of_birth`, `sex`, `genotype`, `strain`, `species`. |
| `nwb.devices` | Neuropixels 1.0 probes (named by serial number) and NewScale manipulators (one per probe). |
| `nwb.electrode_groups["probeA"]` | One group per inserted probe; `location` is the insertion hole label, `device` links to the probe. |
| `nwb.electrodes` | One row per channel: `group_name` (probe), `channel` (0 at the tip), `rel_x`, `rel_y` (µm on the probe), `x`, `y`, `z` (CCF µm), `structure`, `location`, `raw_structure`, `imp`, `reference`. |

### `intervals`: what happened when

Each table has `start_time` and `stop_time` per row.

**`epochs`**: the phases of a session. `script_name` identifies the task or stimulus program
(`DynamicRouting1` is the behavior task, ~1 hour); `interval_names` lists the other interval tables that
hold trials from that epoch.

**`trials`**: one row per trial of the Dynamic Routing task. Also available as `nwb.trials`.
The columns fall into groups:

| Group | Columns |
|---|---|
| Trial timing | `start_time`, `stop_time`, `quiescent_start_time`, `quiescent_stop_time`, `stim_start_time`, `stim_stop_time`, `response_window_start_time`, `response_window_stop_time`, `post_response_window_start_time`, `post_response_window_stop_time` |
| Behavior events | `response_time` (first lick in the response window), `task_control_response_time`, `reward_time` |
| Stimulus and block | `stim_name` (`vis1`, `vis2`, `sound1`, `sound2`, `catch`), `grating_phase`, `rewarded_modality` (`vis` / `aud`), `block_index`, `trial_index`, `trial_index_in_block`, `repeat_index` |
| Outcome flags | `is_response`, `is_hit`, `is_miss`, `is_false_alarm`, `is_correct_reject`, `is_correct`, `is_incorrect`, `is_task_control_correct` |
| Trial type flags | `is_go`, `is_nogo`, `is_target`, `is_nontarget`, `is_vis_target`, `is_aud_target`, `is_vis_nontarget`, `is_aud_nontarget`, `is_vis_stim`, `is_aud_stim`, `is_catch`, `is_vis_rewarded`, `is_aud_rewarded` |
| Reward and block flags | `is_rewarded`, `is_contingent_reward`, `is_noncontingent_reward`, `is_reward_scheduled`, `is_instruction`, `is_block_switch`, `is_repeat`, `is_opto` |

The trial phases described in the [README](README.md#trial-structure) map onto these columns:

| Trial phase | Columns |
|---|---|
| Quiescent period (licking restarts the trial) | `quiescent_start_time` → `quiescent_stop_time` |
| Stimulus | `stim_start_time` → `stim_stop_time` |
| Response window | `response_window_start_time` → `response_window_stop_time` |
| Post-response window | `post_response_window_start_time` → `post_response_window_stop_time` |
| Lick and reward | `response_time` (first lick in the response window, `NaN` if none), `reward_time` (`NaN` if no reward) |

And the trial types onto these flags:

| Trial type | Flag | Outcome flags |
|---|---|---|
| Go (target of the rewarded modality) | `is_go` | `is_hit` (lick) / `is_miss` (no lick) |
| No-go (any other stimulus; excludes catch trials) | `is_nogo` | `is_false_alarm` (lick) / `is_correct_reject` (no lick) |
| Catch (no stimulus) | `is_catch` | `is_response` (lick) |
| Instruction trials at the start of a block | `is_instruction` | `is_contingent_reward` / `is_noncontingent_reward` |

Other flags: `is_reward_scheduled` (a non-contingent reward was scheduled, whether or not it was delivered),
`is_repeat` (the trial repeats the previous one after a miss; `repeat_index` counts the repeats),
`is_opto` (optogenetic inactivation during the trial).

**`performance`** (one row per block): pre-computed behavior summary: `n_trials`, `n_responses`, `n_hits`,
`hit_rate`, `false_alarm_rate`, `catch_response_rate`, `{vis,aud}_{target,nontarget}_response_rate`,
`vis_dprime`, `aud_dprime`, `cross_modality_dprime`, `signed_cross_modality_dprime`, `rewarded_modality`.

**`vis_rf_mapping_trials`, `aud_rf_mapping_trials`**: receptive-field mapping stimuli shown outside the task
(gratings and flashes; tones and noise), with stimulus parameters per trial.

**`optotagging_trials`**: optogenetic stimulation trials, with `stim_name`, `power`, `wavelength`, `location`,
and baseline / response windows that already exclude the light-onset artifact.

### `units`: spike-sorted neurons

One row per unit from Kilosort 2.5. Use `is_qc_pass` to keep well-isolated, stable units.

| Group | Columns |
|---|---|
| Identity | `unit_id` (unique across sessions), `cluster_id`, `electrode_group_name`, `device_name`, `peak_channel`, `peak_electrode` |
| Location | `structure`, `location`, `ccf_ap`, `ccf_dv`, `ccf_ml` |
| Spikes | `spike_times` (ragged: seconds), `spike_amplitudes` (ragged; large), `obs_intervals`, `num_spikes`, `firing_rate` |
| Quality control | `is_qc_pass`, `default_qc`, `decoder_label`, `decoder_probability`, `is_not_drift`, `activity_drift`, `presence_ratio`, `amplitude_cutoff`, `isi_violations_ratio`, `isi_violations_count`, `rp_contamination`, `rp_violations`, `sliding_rp_violation`, `snr`, `d_prime`, `l_ratio`, `isolation_distance`, `silhouette`, `nn_hit_rate`, `nn_miss_rate`, `drift_ptp`, `drift_std`, `drift_mad`, `firing_range`, `amplitude_cv_median`, `amplitude_cv_range`, `sync_spike_2/4/8` |
| Waveform shape | `amplitude`, `amplitude_median`, `half_width`, `peak_to_valley`, `peak_trough_ratio`, `repolarization_slope`, `recovery_slope`, `num_positive_peaks`, `num_negative_peaks`, `spread`, `velocity_above`, `velocity_below`, `exp_decay` |

Load the table without its largest columns:

```python
units = nwb.units.to_dataframe(exclude={"spike_amplitudes", "electrode_group"})
```

### `processing["behavior"]`: processed behavior

| Name | Type | Contents |
|---|---|---|
| `running_speed` | TimeSeries | Forward running speed on the disk, cm/s, low-pass filtered at 4 Hz. Sampled at ~60 Hz. |
| `licks` | DynamicTable | One row per contact with the lick spout: `timestamps`, `duration`, `is_likely_lick` (contacts may include grooming). |
| `rewards` | DynamicTable | One row per water reward: `timestamps`, `duration`, `is_solenoid_time`. |
| `quiescent_interval_violations` | DynamicTable | `timestamps` of licks during the pre-trial quiescent period, which restart the trial. |
| `lp_side_camera`, `lp_front_camera` | DynamicTable | [Lightning Pose](https://doi.org/10.1038/s41592-024-02319-1) face keypoints, one row per video frame. 11 keypoints (`ear_base_l`, `ear_tip_l`, `eye_bottom_l`, `eye_top_l`, `jaw`, `nose_tip`, `nostril_l`, `tongue_base_l`, `tongue_tip`, `whisker_pad_l_side`, `whisker_pad_l_top`), each with `_x`, `_y` (pixels), `_likelihood` (0–1), `_pca_error`, `_temporal_norm`; plus `timestamps`. |
| `dlc_eye_camera` | DynamicTable | DeepLabCut eye keypoints, one row per frame: `cr1–12`, `eye1–12`, `pupil1–12`, each with `_x`, `_y`, `_likelihood`. |
| `eye_tracking` | DynamicTable | Ellipses fit to the pupil, eyelid (`eye`) and corneal reflection (`cr`) per frame: `_center_x`, `_center_y`, `_width`, `_height`, `_phi`, `_area`, `_average_confidence`, `_is_bad_frame`. |
| `facemap_side_camera`, `facemap_front_camera` | TimeSeries | Facemap motion SVD: data is frames x 500 components (float32, ~0.9 GB each). Load a slice, e.g. `.data[:, :10]`. |

Load only the keypoint columns you need, since the pose tables are large:

```python
lp = nwb.processing["behavior"]["lp_side_camera"]
keep = {"timestamps", "ear_base_l_y", "ear_base_l_likelihood"}
ear = lp.to_dataframe(exclude=set(lp.colnames) - keep)
```

### `acquisition`

| Name | Contents |
|---|---|
| `frametimes_eye_camera`, `frametimes_front_camera`, `frametimes_side_camera` | Start time of each video frame exposure (`timestamps`). |
| `manipulator_positions` | Probe manipulator positions at recording time: `electrode_group_name`, `device_name`, `last_movement_time`, `x`, `y`, `z` (µm). |

<h1 align="center">Dynamic Routing</h1>
<h1 align="center">Allen Institute / Neural Dynamics</h1>

Source: https://github.com/AllenNeuralDynamics/conect-dev-capsule

## Documentation

| Document | Description |
|---|---|
| README | Overview of the project, dynamic routing task, and dataset |
| [Tutorial notebook](code/sfn-tutorial-revised.ipynb) | Load a session and plot the main data types |
| [NWB_FILE_GUIDE.md](NWB_FILE_GUIDE.md) | Explains the NWB file organization and structure
| Data dictionary | Full description of data: shape, units, value range, description. 
| [REMOTE.md](REMOTE.md) | Access the data outside of Code Ocean |

---

## Project overview
The Dynamic Routing project aims to uncover the neural mechanisms of flexible decision making. We train mice to perform a visual–auditory switching task in which the rewarded sensory modality alternates within a session, requiring mice to dynamically route sensory information to appropriate motor outputs depending on behavioral context. While mice perform this task, we record from neurons across the mouse brain to identify the neural correlates of flexible sensory-motor associations and to understand how context representations are generated, maintained, and used to guide behavior.

--- 

## Recording strategy
We insert up to six Neuropixels 1.0 (NP 1.0) probes simultaneously across the mouse brain using the **SHIELD implant** ([Bennett et al., *Neuron* 2024](https://doi.org/10.1016/j.neuron.2024.06.015)), a chronic implant system that enables repeatable, multi-probe access to dorsal cortex and underlying structures. Probes are inserted at varying angles and anterior-posterior positions to achieve broad coverage spanning cortical, thalamic, basal ganglia, and midbrain structures (among others). This approach allows us to simultaneously sample the activity of hundreds of neurons across functionally distinct brain regions while the mouse performs our switching task.

| ![SHIELD implant with multiple Neuropixels probes](code/images/SHIELD_diagram.png) | ![Brain-wide coverage of probe insertions](code/images/brainwide_recording.png) |
|---|---|
| *Diagram of SHIELD implant with multiple Neuropixels 1.0 probes.* | *Probe trajectories across mice and sessions showing dense coverage of left hemisphere.* |

### Commonly Recorded Areas Across Sessions

The most frequently recorded areas with QC-passing units include:

- **Frontal cortex**: MOs (secondary motor), FRP (frontal pole), ACAd/ACAv (anterior cingulate), MOp (primary motor)
- **Somatosensory cortex**: SSp (primary), SSs (supplemental)
- **Prefrontal / orbitofrontal**: ORBvl, ORBl, ORBm, ILA (infralimbic), PL (prelimbic)
- **Visual cortex**: VISp, VISal, VISam, VISrl, VISli, VISpm
- **Auditory cortex**: AUDp (primary), AUDd (dorsal), AUDv (ventral), AUDpo (posterior)
- **Temporal association**: TEa, ECT (ectorhinal), PERI (perirhinal)
- **Hippocampus**: CA1, CA2, CA3, DG
- **Lateral septum**: LSr, LSc
- **Striatum**: CP (caudoputamen)
- **Thalamus**: AD (anterodorsal), AV (anteroventral)
- **Midbrain / superior colliculus**: SCig, SCiw, SCsg, SCop, SCdg, SCzo, SCdw
- **Olfactory**: AON, OLF, TTd, MOB, DP
- **Other**: GU (gustatory), RSPv/RSPd (retrosplenial), PAG, PPT, HPF, MB

---

### Session Structure (Epochs)

Each recording session follows a standardized sequence of epochs:

1. **RFMapping** (~15 min) — Receptive field mapping with visual and auditory stimuli
2. **OptoTagging** (~3–6 min) — Optogenetic identification of genetically-defined neurons (pre-task)
3. **Spontaneous** (~10 min) — Spontaneous activity, no stimuli
4. **SpontaneousRewards** (~10 min) — Spontaneous activity with non-contingent rewards
5. **DynamicRouting1** (~60 min) — Main behavioral task
6. **SpontaneousRewards** (~10 min) — Post-task spontaneous with rewards
7. **OptoTagging** (~3–6 min) — Post-task optotagging (some sessions)
8. **Spontaneous** (~10 min) — Post-task spontaneous (some sessions)

---

## Dynamic Routing Task (DynamicRouting1)

Mice perform a **visual-auditory context-switching task** in which the rewarded stimulus modality alternates across blocks within each session.

### Context Blocks and Rule Switching

The session is divided into **6 blocks** (indices 0–5), alternating between two rewarded-modality contexts:

- **Visual context** (`rewarded_modality = "vis"`): The mouse must lick to visual targets (`vis+` → go) and withhold licking to all other stimuli (including auditory targets `aud+` → no-go).
- **Auditory context** (`rewarded_modality = "aud"`): The mouse must lick to auditory targets (`aud+` → go) and withhold licking to all other stimuli (including visual targets `vis+` → no-go).

Some sessions begin with visual blocks first, others with auditory blocks first. Each modality context has 3 blocks per session.

## Trial Structure

Each trial proceeds through the following phases:

1. **Quiescent period** (`quiescent_start_time` → `quiescent_stop_time`): The mouse must remain still (no licking) before a stimulus is presented. Violations restart the quiescent period.
2. **Stimulus presentation** (`stim_start_time` → `stim_stop_time`): A visual grating, auditory stimulus, or catch (blank) is presented.
3. **Response window** (`response_window_start_time` → `response_window_stop_time`): The mouse can lick to report detection. A lick within this window on a go trial is a **hit**; on a no-go trial it is a **false alarm**.
4. **Post-response window** (`post_response_window_start_time` → `post_response_window_stop_time`): Brief post-response period.
5. **Reward** (`reward_time`, if applicable): Water reward delivered on correct go responses (hits) and on some instruction/auto-reward trials.

### Trial Types

| Trial Type | Description |
|------------|-------------|
| **Go** | Target stimulus in the currently rewarded modality; lick = hit, no lick = miss |
| **No-go** | Non-target stimulus, or target in non-rewarded modality; lick = false alarm, no lick = correct reject |
| **Catch** | No stimulus; used to measure baseline lick rate |
| **Instruction** | Auto-rewarded trials (30 per session) at block transitions to cue the new rule |

Additional trial flags: `is_repeat` (repeated after a miss), `is_opto` (optogenetic stimulation applied — 0 opto trials in these task sessions), `is_contingent_reward` / `is_noncontingent_reward`.

---

## Data

Each session is packaged as a data asset in `/data`, containing:
- an NWB file (`<subject>_<date>.nwb.zarr`) with the task trials, spike-sorted units, probe metadata and processed behavior. See [NWB_FILE_GUIDE.md](NWB_FILE_GUIDE.md) for its organization.
- AIND metadata `.json` files

`/data/metadata/dynamic_routing_metadata.csv` lists the sessions in the dataset.

`units_by_area("/root/capsule/data")` returns the number of QC-passing units per brain area (rows) in each session (columns).

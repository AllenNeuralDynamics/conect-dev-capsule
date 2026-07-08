---
name: analyzing-dynamic-routing-data
description: Use this skill when analyzing Dynamic Routing behavior, ephys, or NWB-derived tables. Trigger this skill to get non-obvious experimental context and analysis gotchas. Trigger for any questions about data access, session types and selection, task or block structure, training-stage differences, quality control, and caveats that could affect interpretation of analyses.
---

## Start Here

Start by identifying the analysis cohort, task variant, training stage, reward logic, and unit
filtering conventions relevant to the question before interpreting behavior, neural responses, or
cross-session comparisons.

Do not assume that a released session belongs in the cohort the user actually wants to analyze.
Dynamic Routing sessions fall into a few broad categories, and released datasets can contain a mix of session types:
1. Brain-wide survey: standard context-switching task with ephys, and no manipulations, with subjects that are "trained".
2. Templeton: control sessions without the context switch (ie a single block, with a single rewarded modality).
3. Behavior-only sessions: standard context-switching task but no ephys.
4. Training sessions: various stages of training history, including pre-switch stages without the switching structure.
5. Manipulation sessions: optogenetic or pharmacological perturbations, with or without ephys, typically with the standard context-switching task structure.
6. Context-naive sessions: ephys sessions with the standard context-switching task structure, but without prior exposure to switching.

Although all released data is "production" quality in terms of how it was collected, sessions with
below-par behavioral performance are still included. 

Because these distinctions are analysis choices, explicitly decide which session types to include
before comparing behavior, neural activity, or learning across sessions.

- Read [references/session-filtering.md](references/session-filtering.md) for details on how to detect session type and filtering on session performance criteria.

---
## DynamicRouting1 ("task") structure
- Read [references/task.md](references/task.md) for trial timing, reward contingencies, block
  structure, instruction-trial rules, and experiment-vs-training differences.

## Aggregation and statistics
- by default, aggregate across sessions per subject, then across subjects
- use non-parametric statistics
- be aware that some areas recorded may have few neurons per session and/or few sessions. Ensure that analyses do not depend on sessions with low neuron counts, for example by setting a minimum neuron count per session and sweeping it, or by using hierarchical statistics that can handle unbalanced data.
- always dump a list of unit_ids that contributed to a result
- always dump a summary table session_id and num_units that contributed to a result.

## Other references
- Read [references/curriculum.md](references/curriculum.md) when the analysis depends on stage 1
  through 4 training history or on what "learned" means behaviorally.
- Read [references/units.md](references/units.md) when filtering units or interpreting
  `activity_drift`, `is_not_drift`, `is_qc_pass`, or waveform channel indexing.

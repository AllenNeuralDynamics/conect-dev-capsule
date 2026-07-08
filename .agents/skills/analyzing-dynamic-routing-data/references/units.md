## Information about the dynamic-routing units table

- `activity_drift` (float) is a measure of slow activity drift over the behavior task (epochs.script_name == DynamicRouting1), which could affect the interpretation of baseline firing rate changes over timescales of minutes to hours. It is NOT related to representational drift in neurons. The cause of drift is not determined, but may be influenced by probe motion or over-splitting of units, rather than actual changes in brain activity, so for some analyses we only consider units with low activity drift. 
- `is_not_drift` (bool) is a binary classification of whether the unit is considered to have "drifted" or not, based on the `activity_drift` metric
- `channels` (list[int]) is the list of channel numbers that the unit was recorded on (ie values between 1-384). These can be used to index into `waveform_mean` and `waveform_sd` (210 x 384) to plot only the channels that contain data.   
- `is_qc_pass` (bool) (formerly `default
_qc`) indicates that a unit meets the following criteria:
  - `isi_violations_ratio` < 0.5
  - `presence_ratio` > 0.8
  - `amplitude_cutoff` < 0.1
  - `decoder_label` != "noise"      # output from SpikeInterface/UnitRefine_noise_neural_classifier
  - `activity_drift` < 0.1          # custom metric for Dynamic Routing units= (see above)
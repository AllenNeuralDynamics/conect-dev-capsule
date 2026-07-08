# optotagging
- The optotagging waveform start and end "ramps" that were intended to reduce light artifact are actually steps due to aliasing, so all they do is increase the actual duration of the stimulus. Always use the following to find the correct duration to add to `stim_start_time`:
    ```python
    def actual_duration() -> pl.Expr:
        nominal = pl.col("duration")
        ramp = 0.001
        rate = 2000E
        zero_padding = 3 # [start of on-ramp(assumes offset == 0), end of off-ramp, lastVal]
        return ((nominal + 2*ramp) * rate).round(mode="half_away_from_zero").add(1).sub(zero_padding).truediv(rate).sub(2/rate)
    ```

- light artifacts in the raw ephys data are propagated backward in time due to application of a bandpass filter that runs forward and backward (scipy.signal.filtfilt) prior to spike sorting. Always censor spikes occurring up to 2.5 ms before and 2.5 ms after stim onset or offset to avoid analyzing artifactual spikes.
- raw ephys data during optotagging stimuli can contain 1500 Hz artifacts that lead to artifactual units: these tend to be filtered out with `decoder_label != "noise"`, but any units with ISI under ~0.7 ms during opto response, with low variance, should be treated with suspicion. These spikes would likely also have a different spike to any occurring spontaneously, which is another giveaway that they are artifactual.
- the onset of long duration optotagging waveforms (0.2 s) is identical to the onset of short duration waveforms (0.01 s), so we can use a truncated version of the long stimulus to increase the number of trials availble for classification analysis. There will obviously not be atifactual spikes from light offset at the end of these truncated responses, so it's only necessary to censor spikes at the start.
- a `stim_name` column exists in `/intervals/optotagging_trials` but its values are always `square`
- the `stim_location` column `/intervals/optotagging_trials` specifies which probe the laser targetted (`probeA`, `probeB`), based on the insertion at the brain surface. The  `electrode_group_name` column in the `units` table specifies which probe a unit was recorded on, with the same naming convention. Although we might expect optotagging responses to be strongest when the stimulus is delivered on the same probe as the unit was recorded on: probes are angled, the laser light can spread, and insertions may be close to each other. In addition, laser targeting may not have been possible for every probe. We should therefore analyze each stimulus location separately and find the one that produced the best response for each unit.
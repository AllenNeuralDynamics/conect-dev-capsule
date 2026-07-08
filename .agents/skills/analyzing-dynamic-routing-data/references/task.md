# Dynamic Routing task
This document provides non-obvious details about the experimental design and data organization to
facilitate analysis.

## Trial structure
Event times below are expressed relative to the stimulus onset time in each trial (t = 0 s).
- Pre-trial interval: duration of 1.5 s + a random amount drawn from a truncated exponential
  distribution with a mean of 1 s and a maximum of 6 s. The start and stop times of this interval
  are not explicitly represented. 
- Quiescent interval: t = -1.5 to 0 s (i.e. the last 1.5 s of the Pre-trial interval). This interval
  is analyzed in closed-loop: if a lick occurs (i.e. a quiescent interval violation), the pre-trial
  interval is extended, ultimately ensuring that the last 1.5 s of the interval does not contain a lick.
- Stimulus onset: t = 0 s (immediately after the quiescent interval)
- Response window: t = 0.1 to 0.5 s
    - A lick within this window is registered as a "response"
    - A response to a rewarded stimulus immediately triggers delivery of a contingent reward (see Instruction trials for an exception to this rule)
- Post-response window interval: t = 1 s to 4 s 
    - In Stages 1 to 3 of training, an additional 3 s of dark screen is added to this interval as a timeout for false alarms. 
Total inter-trial interval (stimulus onset to onset): variable, 5.5 to 12 s

## Rewards
- 3 to 5 µL of water
- volume varies due to technical variability in solenoid valve opening time.

## Instruction trials
- Presentation of a rewarded target stimulus, at the start of a block or after 10 consecutive miss trials, with two variants:
    ### 1. experiments with the keyword `early_autorewards` (up to and including 2023-08-03) 
    A non-contingent reward is triggered 0.1 s after stimulus onset, giving the mouse no chance to
    respond before receiving the reward.
    ### 2. experiments with the keyword `late_autorewards` (from 2023-08-09 onward)
    A non-contingent reward is scheduled for delivery at the end of the response window, but if the
    mouse responds within the response window the scheduled reward is cancelled and a contingent
    reward is delivered immediately, as in regular trials. 
    
## Block structure for switching task (Stages 3 & 4)
- 6 blocks per session, 10 minutes each, median 90 trials per block (varies due to random pre-trial interval and quiescent interval violations). 
- 1 of 2 target stimuli is rewarded in a block. The rewarded target alternates each block. All other
  stimuli are unrewarded. The target rewarded in the first block is counterbalanced across sessions.
- 5 instruction trials at the start of the block present the newly-rewarded target stimulus with non-contingent rewards available.
- At the start of the block, there is no information to indicate that the block has changed until
  the first reward is delivered.
- After the instruction trials, presentations of the 4 stimuli are shuffled (even sampling in sub-blocks of 20 trials).
- Catch trials (blank grey screen, no auditory stimulus) are presented with a probability of 0.1.
- An instruction trial is provided after 10 consecutive miss trials (rare).

## Stimuli
- Visual: square grating, 50° diameter, 0.04 cycles/°, 2 cycles/s, latency = display lag
    - Target (vis1): vertical grating, rightward motion
    - Non-target (vis2): horizontal grating, downward motion
- Auditory: amplitude-modulated noise, bandpass 2 to 20 kHz, 5 ms Hanning window, 68 dB, latency = 0 to 70 ms (depends on sound card or DAQ used)
    - Target (sound1): 12 Hz noise
    - Non-target (sound2): 70 Hz noise


- # TODO reward click sound
- # TODO Cluster E differences
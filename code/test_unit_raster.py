import pathlib
import sys
import time

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

sys.path.insert(0, 'code')
import unit_raster_psth_plot as plotter
import nwb_access

unit_id = nwb_access.SPECIFIC_UNIT_IDS[2]
configs = [
    dict(
        unit_id="668755_2023-08-31_B-68",
        max_psth_spike_rate=20,
    ),
    dict(
        unit_id="668755_2023-08-31_B-213",
        max_psth_spike_rate=60,
    ),
]
config = configs[-1]
print(f"Plotting unit {config['unit_id']}...")

output = pathlib.Path('results') / f'example_unit_raster_psth_{config["unit_id"]}.png'
t0 = time.time()
fig = plotter.plot(
    **config,
    stim_names=('sound1', 'vis1', 'sound2', 'vis2'),
    with_instruction_trial_whitespace=True,
    zarr=False,
    show_event_marker_legend=True,
)
print(f"Elapsed time: {time.time() - t0:.2f} seconds")
fig.savefig(output, dpi=300, bbox_inches='tight')
plt.close(fig)
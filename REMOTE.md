# Remote data access
Although this hackathon is focused on local data access from within Code Ocean, it is possible to access the data outside of Code Ocean by streaming it directly from the Allen Institute's open data bucket. 

We've provided [/code/remote/dynamic_routing_tutorial_remote.ipynb](code/remote/dynamic_routing_tutorial_remote.ipynb), demonstrating the data access patterns from the main tutorial using an experimental fast NWB streaming library. 

## Setup
1. Clone the repository and navigate to the `code/remote` directory:
    ```bash
    git clone https://github.com/AllenNeuralDynamics/conect-dev-capsule.git
    cd conect-dev-capsule/code/remote
    ```
2. Create a virtual environment and install the required dependencies (`uv` recommended: https://docs.astral.sh/uv/getting-started/installation/):
    ```bash
    uv sync
    ```
3. Open the notebook and use the newly-created `.venv` virtual envrionment as your kernel
4. No credentials are required to access the data, provided "anon" access to S3 buckets is enabled in relevant Python libraries.

## Help
Please contact ben.hardcastle@alleninstitute.org or message us on the slack channel for assistance.
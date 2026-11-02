# hash:sha256:f60e165c5274577240495febc1a352c5527a06a3aa126630b460ff46f32260fa
ARG REGISTRY_HOST
FROM $REGISTRY_HOST/codeocean/code-server-python-extensions-pack:code-server4.129.0python3.12.4codeocean-mcp-serveruvpyreflyetc

ARG DEBIAN_FRONTEND=noninteractive
ARG GIT_ASKPASS
COPY git-ask-pass /

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential=12.9ubuntu3 \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=secret,id=git-access-token \
    GIT_ACCESS_TOKEN="$(cat /run/secrets/git-access-token)" \
    pip3 install -U --no-cache-dir \
    aind-data-access-api==1.2.1 \
    hdmf-zarr==0.12.0 \
    lazynwb==1.0.0.dev3 \
    matplotlib==3.11.2 \
    numpy==2.5.4 \
    pandas==3.1.0 \
    polars==2.1.0 \
    pynrrd==1.1.3 \
    pynwb==3.1.3 \
    -e git+https://github.com/AllenNeuralDynamics/brainglobe-atlasapi@2b3fed883c20184bdf921e294450c8a4054049c1#egg=brainglobe-atlasapi

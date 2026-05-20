# hash:sha256:ef0a03f00fcb6de4019d48eade4f62abc5efe98d00addce01ba67246b0093f99
ARG REGISTRY_HOST
FROM $REGISTRY_HOST/codeocean/mambaforge3:23.1.0-4-python3.10.12-ubuntu22.04

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
    altair==6.1.0 \
    hdmf-zarr==0.12.0 \
    lazynwb==1.0.0.dev3 \
    matplotlib==3.10.9 \
    pynwb==3.1.3 \
    seaborn==0.13.2 \
    vl-convert-python==1.9.0.post1 \
    -e git+https://github.com/AllenNeuralDynamics/brainglobe-atlasapi@2b3fed883c20184bdf921e294450c8a4054049c1#egg=brainglobe-atlasapi

COPY postInstall /
RUN --mount=type=secret,id=secrets . /run/secrets/secrets \
    && /postInstall

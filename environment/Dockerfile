# hash:sha256:6eba67ef6acb6ea092295fdbf7ee9dc4a40b9851ed33336219e247da5d133359
ARG REGISTRY_HOST
FROM $REGISTRY_HOST/codeocean/mambaforge3:23.1.0-4-python3.10.12-ubuntu22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG GIT_ASKPASS
COPY git-ask-pass /

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential=12.9ubuntu3 \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install -U --no-cache-dir \
    altair==6.1.0 \
    hdmf-zarr==0.12.0 \
    lazynwb==1.0.0.dev5 \
    matplotlib==3.10.9 \
    pynwb==3.1.3 \
    seaborn==0.13.2 \
    vl-convert-python==1.9.0.post1

COPY postInstall /
RUN --mount=type=secret,id=secrets . /run/secrets/secrets \
    && /postInstall

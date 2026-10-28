# hash:sha256:4fd8859c60baab8afc76a4f742ff8e7c77e74e52ca1bbe675e1ae30d0644fadd
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
    matplotlib==3.10.9 \
    pynwb==3.1.3 \
    seaborn==0.13.2 \
    vl-convert-python==1.9.0.post1 \
    -e git+https://github.com/AllenNeuralDynamics/brainglobe-atlasapi@2b3fed883c20184bdf921e294450c8a4054049c1#egg=brainglobe-atlasapi

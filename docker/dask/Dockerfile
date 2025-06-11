ARG PYTHON_VERSION=3.12

FROM ghcr.io/dask/dask:2025.5.1-py${PYTHON_VERSION}

COPY environment.txt /opt/fleet/
RUN mamba install -y --file /opt/fleet/environment.txt \
    && mamba clean -afy \

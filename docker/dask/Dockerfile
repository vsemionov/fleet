ARG PYTHON_VERSION=3.12

FROM daskdev/dask:2025.5.1-py${PYTHON_VERSION}

COPY environment.yml /opt/fleet/
RUN mamba env update -n base -f /opt/fleet/environment.yml \
    && mamba clean -afy

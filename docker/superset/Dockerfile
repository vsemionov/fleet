FROM apache/superset:4.1.2

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        zip unzip \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /opt/fleet/
RUN pip install --no-cache-dir -r /opt/fleet/requirements.txt
USER superset

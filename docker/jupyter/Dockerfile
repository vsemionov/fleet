FROM quay.io/jupyter/scipy-notebook:2025-06-02

ARG JAVA_VERSION=17

USER root

COPY Aptfile /opt/fleet/
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        openjdk-${JAVA_VERSION}-jre-headless \
    && apt-get install -y $(cat /opt/fleet/Aptfile | grep -v '#') \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-${JAVA_VERSION}-openjdk-amd64

USER ${NB_UID}

COPY environment.yml /opt/fleet/
RUN ln -s /opt/fleet/environment.yml /home/${NB_USER}/ \
    && mamba env update -n base -f /home/${NB_USER}/environment.yml \
    && mamba clean -afy \
    && rm /home/${NB_USER}/environment.yml

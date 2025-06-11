FROM condaforge/miniforge3:25.3.0-3

ARG JAVA_VERSION=17

WORKDIR /opt/fleet

COPY Aptfile .
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        openjdk-${JAVA_VERSION}-jre-headless \
    && apt-get install -y $(cat Aptfile | grep -v '#') \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-${JAVA_VERSION}-openjdk-amd64

COPY environment.yml .
RUN conda env create -f environment.yml \
    && conda clean -afy

EXPOSE 8888

CMD ["/opt/conda/envs/fleet/bin/jupyter", "lab", "--allow-root", "--ip=0.0.0.0", "--LabApp.token="]

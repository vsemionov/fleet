ARG JAVA_VERSION=17
ARG SCALA_VERSION=2.12

FROM spark:3.5.6-scala${SCALA_VERSION}-java${JAVA_VERSION}-python3-ubuntu

ARG PYTHON_VERSION=3.12

USER root

RUN apt-get update \
    && apt-get install -y \
        software-properties-common \
    && add-apt-repository -y \
        ppa:deadsnakes/ppa \
    && apt-get install -y \
        python${PYTHON_VERSION} \
        python${PYTHON_VERSION}-venv \
    && apt-get remove -y \
        software-properties-common \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /opt/fleet/
RUN python${PYTHON_VERSION} -m ensurepip --upgrade \
    && python${PYTHON_VERSION} -m pip install --no-cache-dir -U pip setuptools \
    && python${PYTHON_VERSION} -m pip install --no-cache-dir -r /opt/fleet/requirements.txt

USER spark

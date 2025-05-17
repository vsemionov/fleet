FROM apache/superset:4.1.2

USER root
COPY requirements.txt /opt/fleet/
RUN pip install --no-cache-dir -r /opt/fleet/requirements.txt
USER superset

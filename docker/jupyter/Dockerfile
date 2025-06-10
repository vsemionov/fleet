FROM condaforge/miniforge3:25.3.0-3

WORKDIR /opt/fleet

COPY environment.yml .
RUN conda env create -f environment.yml \
    && conda clean -afy

EXPOSE 8888

CMD ["/opt/conda/envs/fleet/bin/jupyter", "lab", "--allow-root", "--ip=0.0.0.0", "--LabApp.token="]

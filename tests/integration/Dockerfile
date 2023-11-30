FROM mambaorg/micromamba

COPY --chown=$MAMBA_USER:$MAMBA_USER environment.yml .

RUN micromamba install --yes -n base --file environment.yml

ARG MAMBA_DOCKERFILE_ACTIVATE=1

COPY --chown=$MAMBA_USER:$MAMBA_USER postprocessing /opt/postprocessing/postprocessing
COPY --chown=$MAMBA_USER:$MAMBA_USER tests/integration/post_processing.conf /etc/autoreduce/post_processing.conf

ENV PYTHONPATH /opt/postprocessing

USER root
RUN mkdir -p /opt/postprocessing/log && \
    mkdir -p /opt/postprocessing/scripts && \
    touch /opt/postprocessing/scripts/oncat_ingest.py && \
    \
    mkdir -p /SNS/EQSANS/IPTS-10674/0/30892/NeXus && \
    mkdir -p /SNS/EQSANS/IPTS-10674/shared/autoreduce && \
    touch /SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs && \
    mkdir -p /SNS/EQSANS/shared/autoreduce && \
    echo "import sys;print(sys.argv[1:])" > /SNS/EQSANS/shared/autoreduce/reduce_EQSANS.py && \
    \
    mkdir -p /SNS/CORELLI/IPTS-15526/nexus && \
    touch /SNS/CORELLI/IPTS-15526/nexus/CORELLI_29666.nxs.h5 && \
    mkdir -p /SNS/CORELLI/shared/autoreduce && \
    echo "raise RuntimeError('This is an ERROR!')" > /SNS/CORELLI/shared/autoreduce/reduce_CORELLI.py && \
    \
    mkdir -p /SNS/TOPAZ/shared/autoreduce && \
    echo "a=0" > /SNS/TOPAZ/shared/autoreduce/reduce_TOPAZ.py && \
    echo "a=1" > /SNS/TOPAZ/shared/autoreduce/reduce_TOPAZ_default.py && \
    echo "a=\${value}" > /SNS/TOPAZ/shared/autoreduce/reduce_TOPAZ.py.template && \
    \
    chown -R $MAMBA_USER:$MAMBA_USER /opt/postprocessing /SNS

USER $MAMBA_USER

CMD /opt/postprocessing/postprocessing/queueProcessor.py

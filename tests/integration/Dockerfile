FROM registry.access.redhat.com/ubi9/ubi

RUN dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm
RUN dnf install -y python3-requests python3-stomppy python3-pip python3-coverage python3-psutil python-unversioned-command

COPY postprocessing /opt/postprocessing/postprocessing
COPY scripts /opt/postprocessing/scripts
COPY pyproject.toml /opt/postprocessing/
COPY tests/integration/post_processing.conf /etc/autoreduce/post_processing.conf

RUN pip install --no-cache-dir /opt/postprocessing/

RUN echo \#\!/bin/bash > /usr/bin/coverage_run && \
    echo coverage run \$@ >> /usr/bin/coverage_run && \
    chmod +x /usr/bin/coverage_run

ENV PYTHONPATH /opt/postprocessing

RUN echo -e "[run]\nsource=postprocessing\nparallel=True\nrelative_files=True" > /opt/postprocessing/.coveragerc
RUN mkdir -p /opt/postprocessing/log && \
    mkdir -p /opt/postprocessing/scripts && \
    touch /opt/postprocessing/scripts/oncat_ingest.py && \
    touch /opt/postprocessing/scripts/oncat_reduced_ingest.py && \
    \
    mkdir -p /SNS/EQSANS/IPTS-10674/0/30892/NeXus && \
    mkdir -p /SNS/EQSANS/IPTS-10674/shared/autoreduce && \
    touch /SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs && \
    touch /SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30893_event.nxs && \
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
    chown -R root:root /opt/postprocessing /SNS

WORKDIR /opt/postprocessing
ENV COVERAGE_PROCESS_START /opt/postprocessing/.coveragerc

CMD ["coverage", "run", "postprocessing/queueProcessor.py"]

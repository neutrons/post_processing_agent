FROM registry.access.redhat.com/ubi9/ubi

RUN dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm
RUN dnf install -y python3-requests python3-stomppy python3-pip python3-coverage python3-psutil python-unversioned-command

COPY tests/integration/python3-pyoncat-2.1-1.noarch.rpm /tmp/
RUN dnf install -y /tmp/python3-pyoncat-2.1-1.noarch.rpm

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
    mkdir -p /SNS/CORELLI/IPTS-15526/shared/autoreduce && \
    echo '{"output_files":[], "input_files": []}' > /SNS/CORELLI/IPTS-15526/shared/autoreduce/CORELLI_29666.json && \
    mkdir -p /SNS/CORELLI/IPTS-15526/images/det_main && \
    touch /SNS/CORELLI/IPTS-15526/images/det_main/CORELLI_29666_det_main_000001.tiff && \
    mkdir -p /SNS/CORELLI/shared/autoreduce && \
    echo "raise RuntimeError('This is an ERROR!')" > /SNS/CORELLI/shared/autoreduce/reduce_CORELLI.py && \
    \
    mkdir -p /SNS/TOPAZ/shared/autoreduce && \
    echo "a=0" > /SNS/TOPAZ/shared/autoreduce/reduce_TOPAZ.py && \
    echo "a=1" > /SNS/TOPAZ/shared/autoreduce/reduce_TOPAZ_default.py && \
    echo "a=\${value}" > /SNS/TOPAZ/shared/autoreduce/reduce_TOPAZ.py.template && \
    \
    mkdir -p /SNS/VENUS/IPTS-99999/nexus && \
    mkdir -p /SNS/VENUS/IPTS-99999/images && \
    mkdir -p /SNS/VENUS/IPTS-99999/shared/autoreduce && \
    touch /SNS/VENUS/IPTS-99999/nexus/VENUS_12345.nxs.h5 && \
    touch /SNS/VENUS/IPTS-99999/nexus/VENUS_12347.nxs.h5 && \
    # Image files are named YYYYMMDD_Run_<run_number>_... by the VENUS DAQ.
    # Runs 12345 and 12347 share this directory, as a series of runs does.
    touch /SNS/VENUS/IPTS-99999/images/20260721_Run_12345_series_0001.fits && \
    touch /SNS/VENUS/IPTS-99999/images/20260721_Run_12345_series_0002.fits && \
    touch /SNS/VENUS/IPTS-99999/images/20260721_Run_12345_series_0003.tiff && \
    touch /SNS/VENUS/IPTS-99999/images/20260721_Run_12347_series_0001.tiff && \
    # TPX3 prepends a second date, so the run token is not at the start of the name
    touch /SNS/VENUS/IPTS-99999/images/20250428_20260721_Run_12345_tpx3_0004.tiff && \
    # Images of another run, and a run number that merely extends 12345:
    # neither belongs to run 12345
    touch /SNS/VENUS/IPTS-99999/images/20260721_Run_12344_series_0001.tiff && \
    touch /SNS/VENUS/IPTS-99999/images/20260721_Run_123450_series_0001.tiff && \
    mkdir -p /SNS/VENUS/shared/autoreduce && \
    echo "# image cataloging enabled for VENUS" > /SNS/VENUS/shared/autoreduce/catalog_VENUS.py && \
    \
    mkdir -p /SNS/IMAGING/IPTS-99999/nexus && \
    mkdir -p /SNS/IMAGING/IPTS-99999/images && \
    mkdir -p /SNS/IMAGING/shared/autoreduce && \
    touch /SNS/IMAGING/IPTS-99999/nexus/IMAGING_12346.nxs.h5 && \
    touch /SNS/IMAGING/IPTS-99999/images/20260721_Run_12346_series_0001.fits && \
    touch /SNS/IMAGING/IPTS-99999/images/20260721_Run_12346_series_0002.fits && \
    \
    chown -R root:root /opt/postprocessing /SNS

WORKDIR /opt/postprocessing
ENV COVERAGE_PROCESS_START /opt/postprocessing/.coveragerc

CMD ["coverage", "run", "postprocessing/queueProcessor.py"]

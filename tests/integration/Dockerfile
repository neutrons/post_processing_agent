FROM condaforge/mambaforge

RUN apt-get update -y
RUN apt-get install gcc -y

COPY environment.yml .

RUN conda env create

COPY postprocessing /opt/postprocessing/postprocessing
COPY configuration/post_process_consumer.conf.local /etc/autoreduce/post_processing.conf
RUN sed -i 's/localhost/activemq/' /etc/autoreduce/post_processing.conf

ENV PYTHONPATH /opt/postprocessing

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
    echo "a=\${value}" > /SNS/TOPAZ/shared/autoreduce/reduce_TOPAZ.py.template

RUN echo "#!/bin/bash" > /usr/bin/run_postprocessing && \
    echo ". activate post_processing_agent_py2" >> /usr/bin/run_postprocessing && \
    echo "/opt/postprocessing/postprocessing/queueProcessor.py" >> /usr/bin/run_postprocessing && \
    chmod +x /usr/bin/run_postprocessing

CMD /usr/bin/run_postprocessing

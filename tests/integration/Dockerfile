FROM condaforge/mambaforge

RUN apt-get update -y
RUN apt-get install gcc -y

COPY environment.yml .

RUN conda env create

RUN mkdir -p /opt/postprocessing/log

COPY postprocessing /opt/postprocessing/postprocessing
COPY configuration/post_process_consumer.conf.local /etc/autoreduce/post_processing.conf
RUN sed -i 's/localhost/activemq/' /etc/autoreduce/post_processing.conf

ENV PYTHONPATH /opt/postprocessing

RUN mkdir -p /SNS/EQSANS/IPTS-10674/0/30892/NeXus
RUN touch /SNS/EQSANS/IPTS-10674/0/30892/NeXus/EQSANS_30892_event.nxs
RUN mkdir -p /SNS/EQSANS/shared/autoreduce
RUN echo "import sys;print(sys.argv[1:])" > /SNS/EQSANS/shared/autoreduce/reduce_EQSANS.py

RUN mkdir -p /SNS/CORELLI/IPTS-15526/nexus
RUN touch /SNS/CORELLI/IPTS-15526/nexus/CORELLI_29666.nxs.h5
RUN mkdir -p /SNS/CORELLI/shared/autoreduce
RUN echo "raise RuntimeError('This is an ERROR!')" > /SNS/CORELLI/shared/autoreduce/reduce_CORELLI.py

RUN echo "#!/bin/bash" > /usr/bin/run_postprocessing && \
    echo ". activate post_processing_agent_py2" >> /usr/bin/run_postprocessing && \
    echo "/opt/postprocessing/postprocessing/queueProcessor.py" >> /usr/bin/run_postprocessing && \
    chmod +x /usr/bin/run_postprocessing

CMD /usr/bin/run_postprocessing

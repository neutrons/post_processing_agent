FROM centos:7

RUN curl http://packages.sns.gov/distros/rhel/7/sns/sns.repo -o /etc/yum.repos.d/sns.repo
RUN yum install -y epel-release
RUN yum updateinfo
RUN yum install -y \
    python-requests \
    python-suds \
    python-twisted-core \
    python-twisted-web \
    python-twisted-words \
    python-stompest \
    python2-stompest-async \
    python-pip \
    nexus \
    nexus-python \
    make \
    numpy

COPY . .
USER postprocessing
RUN mkdir /SNS
RUN chown postprocessing:postprocessing /SNS

RUN make install

RUN cp configuration/post_process_consumer.conf.development /etc/autoreduce/post_processing.conf

# This configuration allows it to run with docker-compose from https://github.com/neutrons/data_workflow
RUN sed -i 's/localhost/activemq/' /etc/autoreduce/post_processing.conf

RUN echo "#!/bin/bash" > /usr/bin/run_postprocessing && \
    echo "/opt/postprocessing/queueProcessor.py &" >> /usr/bin/run_postprocessing && \
    echo "sleep 1" >> /usr/bin/run_postprocessing && \
    echo "tail -F /opt/postprocessing/log/postprocessing.log" >> /usr/bin/run_postprocessing && \
    chmod +x /usr/bin/run_postprocessing

CMD run_postprocessing

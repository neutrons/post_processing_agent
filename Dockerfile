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

# setup the host user
#ARG USER=postprocessing
ARG DATA_TARBALL=/tmp/SNSdata.tar.gz
#ARG UID=1000
#ARG GID=1000
#RUN echo "USER ${users} or ${user} or $(id -g) or $(id -u)"
#RUN echo "UID ${UID} GID ${GID}"
#RUN groupadd postprocessing --gid ${GID} && useradd -u ${UID} -G postprocessing -D postprocessing
#USER ${UID}:${GID}
USER ${USER}
RUN echo "CURRENT_UID ${CURRENT_UID} or $(id -g) or $(id -u) or $(whoami)"
# copy a test data image into place
RUN mkdir /SNS
#RUN chown postprocessing:postprocessing /SNS
RUN echo "DATA_TARBALL ${DATA_TARBALL}"
RUN ls /tmp
RUN ls /*.gz
RUN ls ${DATA_TARBALL}
RUN test -f ${DATA_TARBALL} && tar xzf --directory=/SNS ${DATA_TARBALL}

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

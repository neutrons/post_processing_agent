FROM --platform=linux/amd64 centos:7 as package

RUN yum install -y \
    make \
    rpm-build

WORKDIR /app

COPY scripts /app/scripts
COPY configuration /app/configuration
COPY postprocessing /app/postprocessing
COPY SPECS /app/SPECS
COPY Makefile /app/


RUN mkdir -p /root/rpmbuild/SOURCES

RUN make rpm

FROM --platform=linux/amd64 centos:7 as app
COPY --from=package /root/rpmbuild/RPMS/noarch/postprocessing-2.6-1.noarch.rpm /postprocessing-2.6-1.noarch.rpm


RUN curl http://packages.sns.gov/distros/rhel/7/sns/sns.repo -o /etc/yum.repos.d/sns.repo
RUN yum install -y epel-release
RUN yum updateinfo

RUN yum install -y /postprocessing-2.6-1.noarch.rpm

# This configuration allows it to run with docker-compose from https://github.com/neutrons/data_workflow
COPY configuration/post_process_consumer.conf.development /etc/autoreduce/post_processing.conf
RUN sed -i 's/localhost/activemq/' /etc/autoreduce/post_processing.conf

RUN echo "#!/bin/bash" > /usr/bin/run_postprocessing && \
    echo "/opt/postprocessing/queueProcessor.py &" >> /usr/bin/run_postprocessing && \
    echo "sleep 1" >> /usr/bin/run_postprocessing && \
    echo "tail -F /opt/postprocessing/log/postprocessing.log" >> /usr/bin/run_postprocessing && \
    chmod +x /usr/bin/run_postprocessing

CMD run_postprocessing

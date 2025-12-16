FROM registry.access.redhat.com/ubi9/ubi

RUN dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm
RUN dnf install -y make rpm-build python3-build python3-pip python-unversioned-command

COPY scripts /app/scripts
COPY configuration /app/configuration
COPY postprocessing /app/postprocessing
COPY pyproject.toml /app/
COPY rpmbuild.sh /app/
COPY README.md /app/
COPY LICENSE.rst /app/
COPY SPECS /app/SPECS
COPY systemd /app/systemd

RUN mkdir -p /root/rpmbuild/SOURCES

# The RPM build assumes that user "snsdata" and groups exist (for testing)
RUN useradd snsdata
# add group "users" only if it doesn't exist
RUN getent group users || groupadd users
# add group "hfiradmin" for HFIR file access
RUN getent group hfiradmin || groupadd hfiradmin

RUN cd /app && ./rpmbuild.sh || exit 1

# manually install python3-pyoncat as dnf install fails due to a missing dependency
COPY tests/integration/python3-pyoncat-2.1-1.noarch.rpm /root/rpmbuild/SOURCES/
RUN dnf install -y /root/rpmbuild/SOURCES/python3-pyoncat-2.1-1.noarch.rpm || exit 1

RUN dnf install -y /root/rpmbuild/RPMS/noarch/postprocessing*.noarch.rpm || exit 1

# This configuration allows it to run with docker compose from https://github.com/neutrons/data_workflow
COPY configuration/post_process_consumer.conf.development /etc/autoreduce/post_processing.conf
RUN sed -i 's/localhost/activemq/' /etc/autoreduce/post_processing.conf

RUN echo "#!/bin/bash" > /usr/bin/run_postprocessing && \
    echo "/opt/postprocessing/queueProcessor.py &" >> /usr/bin/run_postprocessing && \
    echo "sleep 1" >> /usr/bin/run_postprocessing && \
    echo "tail -F /opt/postprocessing/log/postprocessing.log" >> /usr/bin/run_postprocessing && \
    chmod +x /usr/bin/run_postprocessing

CMD ["run_postprocessing"]

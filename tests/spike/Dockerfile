FROM registry.access.redhat.com/ubi9/ubi
# EPEL's qpid-proton uses Cyrus SASL, which needs cyrus-sasl-plain for username/password logins
RUN dnf install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-9.noarch.rpm \
 && dnf install -y python3-qpid-proton python3-stomppy python3-requests cyrus-sasl-plain \
 && dnf clean all
# The spike runs from a mounted host directory, so don't leave root-owned __pycache__ in it
ENV PYTHONDONTWRITEBYTECODE=1
WORKDIR /spike

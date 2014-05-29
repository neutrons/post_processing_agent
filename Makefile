prefix := /opt/postprocessing
sysconfig := /etc/autoreduce
bindir := /usr/bin

ifeq ($(OS),Windows_NT)
UNAME_S=Windows
else
UNAME_S := $(shell uname -s)
ifeq ($(UNAME_S),Linux)
ISLINUX = 1
endif
ifeq ($(UNAME_S),Darwin)
ISOSX = 1
endif
endif

all: postproc
	
check:
	# Check dependencies
	@python -c "import xml.utils.iso8601" || echo "ERROR: Need PyXML: easy_install PyXML"
	@python -c "import requests" || echo "ERROR: Need requests: easy_install requests"
	@python -c "import stompest" || echo "ERROR: Need stompest: easy_install stompest"
	@python -c "import stompest.async" || echo "ERROR: Need stompest.async: easy_install stompest.async"
	@python -c "import suds" || echo "ERROR: Need suds: easy_install suds"
	@python -c "import nxs" || echo "ERROR: Need nexus: http://download.nexusformat.org/kits/"

	@test -f configuration/icatclient.properties || echo -e "\n===> SET UP configuration/icatclient.properties BEFORE INSTALLATION\n";
	@test -f configuration/post_process_consumer.conf || echo -e "\n===> SET UP configuration/post_process_consumer.conf BEFORE INSTALLATION\n";
	
install: postproc

postproc: check
	# Make sure the directories exist
	@test -d $(sysconfig) || mkdir -m 0755 -p $(sysconfig)
	@test -d /var/log/SNS_applications || mkdir -m 0755 /var/log/SNS_applications
	@test -d $(prefix) || mkdir -m 0755 $(prefix)
	@test -d $(prefix)/postprocessing || mkdir -m 0755 $(prefix)/postprocessing
	@test -d $(prefix)/log || mkdir -m 0755 $(prefix)/log
	@test -d $(prefix)/scripts || mkdir -m 0755 $(prefix)/scripts
	
	# Install application code
	install -m 664	configuration/icat4.cfg $(sysconfig)/icat4.cfg
	install -m 664	configuration/icatclient.properties $(sysconfig)/icatclient.properties
	install -m 664	configuration/post_process_consumer.conf $(sysconfig)/post_process_consumer.conf
	install -m 755	postprocessing/__init__.py	 $(prefix)/postprocessing/__init__.py
	install -m 755	postprocessing/Consumer.py	 $(prefix)/postprocessing/Consumer.py
	install -m 755	postprocessing/queueProcessor.py	$(bindir)/queueProcessor.py
	install -m 755	postprocessing/Configuration.py	 $(prefix)/postprocessing/Configuration.py
	install -m 755	postprocessing/PostProcessAdmin.py	 $(prefix)/postprocessing/PostProcessAdmin.py
	install -m 755	postprocessing/ingest_nexus.py	 $(prefix)/postprocessing/ingest_nexus.py
	install -m 755	postprocessing/ingest_reduced.py	 $(prefix)/postprocessing/ingest_reduced.py
	install -m 755	scripts/remoteJob.sh	 $(prefix)/scripts/remoteJob.sh
	install -m 755	scripts/startJob.sh	 $(prefix)/scripts/startJob.sh

rpm:
	@echo "Creating RPMs"
	@rm -rf build
	mkdir build
	mkdir build/postprocessing
	cp -pr Makefile build/postprocessing
	cp -pr scripts build/postprocessing
	cp -pr configuration build/postprocessing
	cp -pr postprocessing build/postprocessing

	cd build;tar -czf ~/rpmbuild/SOURCES/postprocessing.tgz postprocessing
	rpmbuild -ba ./SPECS/postprocessing.spec
	
.PHONY: check
.PHONY: install
.PHONY: postproc

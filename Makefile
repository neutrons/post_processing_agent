prefix := /opt/postprocessing
#prefix := /sw/fermi/autoreduce

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
	@python -c "import xml.utils.iso8601" || echo "\nERROR: Need PyXML: easy_install PyXML\n"
	@python -c "import requests" || echo "\nERROR: Need requests: easy_install requests\n"
	@python -c "import stompest" || echo "\nERROR: Need stompest: easy_install stompest\n"
	@python -c "import stompest.async" || echo "\nERROR: Need stompest.async: easy_install stompest.async\n"
	@python -c "import suds" || echo "\nERROR: Need suds: easy_install suds\n"
	@python -c "import nxs" || echo "\nERROR: Need nexus: http://download.nexusformat.org/kits/\n"
	
install: postproc

postproc: check
	@echo "Installing post-processing service"
	# Make sure the directories exist
	test -d /etc/autoreduce || mkdir -m 0755 -p /etc/autoreduce
	test -d /var/log/SNS_applications || mkdir -m 0755 /var/log/SNS_applications
	test -d $(prefix) || mkdir -m 0755 $(prefix)
	test -d $(prefix)/postprocessing || mkdir -m 0755 $(prefix)/postprocessing
	test -d $(prefix)/log || mkdir -m 0755 $(prefix)/log
	test -d $(prefix)/scripts || mkdir -m 0755 $(prefix)/scripts
	test -d $(prefix)/config || mkdir -m 0755 $(prefix)/config
	
	# Install application code
	# install -m 664	configuration/icat4.cfg	 /etc/autoreduce/icat4.cfg
	# For backward compatibility, install the configuration where hooks into the post-processing can find it
	# install -m 664	configuration/post_process_consumer.conf.dev /etc/autoreduce/post_process_consumer.conf
	install -m 664	configuration/post_process_consumer.conf.dev $(prefix)/config/post_process_consumer.conf
	install -m 755	postprocessing/__init__.py	 $(prefix)/postprocessing/__init__.py
	install -m 755	postprocessing/Consumer.py	 $(prefix)/postprocessing/Consumer.py
	install -m 755	postprocessing/queueProcessor.py	 /usr/bin/queueProcessor.py
	install -m 755	postprocessing/Configuration.py	 $(prefix)/postprocessing/Configuration.py
	install -m 755	postprocessing/PostProcessAdmin.py	 $(prefix)/postprocessing/PostProcessAdmin.py
	install -m 755	postprocessing/ingest_nexus.py	 $(prefix)/postprocessing/ingest_nexus.py
	install -m 755	postprocessing/ingest_reduced.py	 $(prefix)/postprocessing/ingest_reduced.py
	install -m 755	scripts/remoteJob.sh	 $(prefix)/scripts/remoteJob.sh
	install -m 755	scripts/startJob.sh	 $(prefix)/scripts/startJob.sh
	
.PHONY: check
.PHONY: install
.PHONY: postproc

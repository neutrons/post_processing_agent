#prefix := /opt/postprocessing
prefix := /sw/fermi/autoreduce/postprocessing
sysconfig := /etc/autoreduce
bindir := /usr/bin
site_packages := `python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())"`

# The installed prefix may be different from the prefix above while building an RPM
installed_prefix = $(prefix)

all: postproc
	
check:
	# Check dependencies
	@python -c "import xml.utils.iso8601" || echo "ERROR: Need PyXML: easy_install PyXML"
	@python -c "import requests" || echo "ERROR: Need requests: easy_install requests"
	@python -c "import stompest" || echo "ERROR: Need stompest: easy_install stompest"
	@python -c "import stompest.async" || echo "ERROR: Need stompest.async: easy_install stompest.async"
	@python -c "import suds" || echo "ERROR: Need suds: easy_install suds"
	@python -c "import nxs" || echo "ERROR: Need nexus: http://download.nexusformat.org/kits/"
	@python -c "import twisted" || echo "ERROR: Need twisted: easy_install twisted"

	@test -f configuration/icatclient.properties || echo -e "\n===> SET UP configuration/icatclient.properties BEFORE INSTALLATION\n";
	@test -f configuration/post_process_consumer.conf || echo -e "\n===> SET UP configuration/post_process_consumer.conf BEFORE INSTALLATION\n";
	
install: config postproc

install/isolated: config/isolated postproc

config:
	# Make sure the directories exist
	@test -d $(sysconfig) || mkdir -m 0755 -p $(sysconfig)
	install -m 664	configuration/icat4.cfg $(sysconfig)/icat4.cfg
	install -m 664	configuration/icatclient.properties $(sysconfig)/icatclient.properties
	install -m 664	configuration/post_process_consumer.conf $(sysconfig)/post_processing.conf
	echo "$(installed_prefix)" > configuration/postprocessing.pth	
	install -m 664 configuration/postprocessing.pth $(site_packages)/postprocessing.pth
	
config/isolated:
	# Simplified configuration for isolated installation - usually remote systems
	@test -d $(prefix)/configuration || mkdir -m 0755 $(prefix)/configuration
	install -m 664	configuration/post_process_consumer.conf $(prefix)/configuration/post_processing.conf
	
postproc: check
	# Make sure the directories exist
	@test -d $(prefix) || mkdir -m 0755 $(prefix)
	@test -d $(prefix)/postprocessing || mkdir -m 0755 $(prefix)/postprocessing
	@test -d $(prefix)/postprocessing/processors || mkdir -m 0755 $(prefix)/postprocessing/processors
	@test -d $(prefix)/log || mkdir -m 0775 $(prefix)/log
	@test -d $(prefix)/scripts || mkdir -m 0755 $(prefix)/scripts
	
	# Install application code
	install -m 755	postprocessing/__init__.py	 $(prefix)/postprocessing/__init__.py
	install -m 755	postprocessing/Consumer.py	 $(prefix)/postprocessing/Consumer.py
	install -m 755	postprocessing/Configuration.py	 $(prefix)/postprocessing/Configuration.py
	install -m 755	postprocessing/PostProcessAdmin.py	 $(prefix)/postprocessing/PostProcessAdmin.py
	install -m 755	postprocessing/ingest_nexus.py	 $(prefix)/postprocessing/ingest_nexus.py
	install -m 755	postprocessing/ingest_reduced.py	 $(prefix)/postprocessing/ingest_reduced.py
	install -m 755	postprocessing/reduction_script_writer.py	 $(prefix)/postprocessing/reduction_script_writer.py
	install -m 755	scripts/remoteJob.sh	 $(prefix)/scripts/remoteJob.sh
	install -m 755	scripts/startJob.sh	 $(prefix)/scripts/startJob.sh
	install -m 755	scripts/mantidpython.py	 $(prefix)/scripts/mantidpython.py
	install -m 755	scripts/run_mantid_algorithm.py	 $(prefix)/scripts/run_mantid_algorithm.py
	install -m 755	postprocessing/queueProcessor.py	$(prefix)/queueProcessor.py
	install -m 755	postprocessing/processors/__init__.py	$(prefix)/postprocessing/processors
	install -m 755	postprocessing/processors/base_processor.py	$(prefix)/postprocessing/processors
	install -m 755	postprocessing/processors/test_processor.py	$(prefix)/postprocessing/processors	
	install -m 755	postprocessing/processors/job_tree.py	$(prefix)/postprocessing/processors
	install -m 755	postprocessing/processors/job_handling.py	$(prefix)/postprocessing/processors
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

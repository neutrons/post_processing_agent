help:
    # this nifty perl one-liner collects all comments headed by the double "#" symbols next to each target and recycles them as comments
	@perl -nle'print $& if m{^[/a-zA-Z_-]+:.*?## .*$$}' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

build/rpm:  ## build RPM inside Docker container and copy RPM and SRPM to this directory
	docker build --network host --tag postprocess .
	CONTAINER_ID=$$(docker run -d --name rpm_builder_container postprocess) && \
	sleep 5 && \
	echo $$CONTAINER_ID && \
	FILES_RPM=$$(docker exec $$CONTAINER_ID sh -c 'ls /root/rpmbuild/RPMS/noarch/*.rpm 2>/dev/null || true') && \
	FILES_SRPM=$$(docker exec $$CONTAINER_ID sh -c 'ls /root/rpmbuild/SRPMS/*.rpm 2>/dev/null || true') && \
	for file in $$FILES_RPM $$FILES_SRPM; do \
		if [ -n "$$file" ]; then docker cp $$CONTAINER_ID:"$$file" .; fi; \
	done && \
	docker stop $$CONTAINER_ID && \
	docker rm $$CONTAINER_ID

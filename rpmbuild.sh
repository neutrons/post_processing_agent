#!/bin/bash
rm -rf dist postprocessing.egg-info
python3 -m build --sdist
cp dist/postprocessing-*.tar.gz ~/rpmbuild/SOURCES/
rpmbuild -ba SPECS/postprocessing.spec
cp ~/rpmbuild/RPMS/noarch/postprocessing-*-*.*.noarch.rpm dist/
cp ~/rpmbuild/SRPMS/postprocessing-*-*.*.src.rpm dist/

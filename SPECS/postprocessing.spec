Summary: postprocessing
Name: postprocessing
Version: 2.5
Release: 1
Group: Applications/Engineering
prefix: /opt/postprocessing
BuildRoot: %{_tmppath}/%{name}
License: Open
Source: postprocessing.tgz
Requires: libNeXus.so.0()(64bit) libc.so.6()(64bit) libc.so.6(GLIBC_2.2.5)(64bit)
Requires: python-suds
Requires: nexus-python
Requires: python-twisted-core
Requires: python-twisted-web
Requires: python-twisted-words
Requires: python-stompest
Requires: python2-stompest-async
Requires: python-requests
%define debug_package %{nil}
%define site_packages %(python -c "from distutils.sysconfig import get_python_lib; print(get_python_lib())")

%description
Post-processing agent to automatically catalog and reduce neutron data

%prep
%setup -q -n %{name}

%build

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}%{_sysconfdir}
mkdir -p %{buildroot}%{_bindir}
mkdir -p %{buildroot}%{prefix}
mkdir -p %{buildroot}%{site_packages}
mkdir -p %{buildroot}/var/log/SNS_applications
make prefix="%{buildroot}%{prefix}" installed_prefix="%{prefix}" site_packages="%{buildroot}%{site_packages}" sysconfig="%{buildroot}%{_sysconfdir}/autoreduce" bindir="%{buildroot}/%{_bindir}" install

%post
chgrp snswheel %{_sysconfdir}/autoreduce/icat4.cfg
chgrp snswheel %{_sysconfdir}/autoreduce/icatclient.properties
chgrp snswheel %{_sysconfdir}/autoreduce/post_processing.conf
chown -R snsdata %{_sysconfdir}/autoreduce
chown -R snsdata %{prefix}
chown -R snsdata /var/log/SNS_applications

%files
%attr(755, -, -) %{prefix}/
%attr(755, -, -) /var/log/SNS_applications
%attr(755, -, -) %{site_packages}/postprocessing.pth

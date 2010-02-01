# test step.package.rpm.*

from twisted.trial import unittest

from buildbot.steps.package.rpm import RpmBuild, RpmLint, RpmSpec


class TestRpmBuild(unittest.TestCase):
    """
    Tests the package.rpm.RpmBuild class.
    """

    def test_creation(self):
        """
        Test that instances are created with proper data.
        """
        rb = RpmBuild()
        self.assertEquals(rb.specfile, None)
        self.assertFalse(rb.autoRelease)
        self.assertFalse(rb.vcsRevision)

        rb2 = RpmBuild('aspec.spec', autoRelease=True, vcsRevision=True)
        self.assertEquals(rb2.specfile, 'aspec.spec')
        self.assertTrue(rb2.autoRelease)
        self.assertTrue(rb2.vcsRevision)

    def test_rpmbuild(self):
        """
        Verifies the rpmbuild string is what we would expect.
        """
        rb = RpmBuild('topdir', 'buildir', 'rpmdir', 'sourcedir',
            'specdir', 'dist')
        expected_result = ('rpmbuild --define "_topdir buildir"'
            ' --define "_builddir rpmdir" --define "_rpmdir sourcedir"'
            ' --define "_sourcedir specdir" --define "_specdir dist"'
            ' --define "_srcrpmdir `pwd`" --define "dist .el5"')
        self.assertEquals(rb.rpmbuild, expected_result)


class TestRpmLint(unittest.TestCase):
    """
    Tests the package.rpm.RpmLint class.
    """

    def test_command(self):
        """
        Test that instance command variable is created with proper data.
        """
        rl = RpmLint()
        expected_result = ["/usr/bin/rpmlint", "-i", '*rpm']
        self.assertEquals(rl.command, expected_result)


class TestRpmSpec(unittest.TestCase):
    """
    Tests the package.rpm.RpmSpec class.
    """

    def test_creation(self):
        """
        Test that instances are created with proper data.
        """
        rs = RpmSpec()
        self.assertEquals(rs.specfile, None)
        self.assertEquals(rs.pkg_name, None)
        self.assertEquals(rs.pkg_version, None)
        self.assertFalse(rs.loaded)

    def test_load(self):
        try:
            from cStringIO import StringIO
        except ImportError, ie:
            from StringIO import StringIO

        specfile = StringIO()
        specfile.write("""\
Name:           example
Version:        1.0.0
Release:        1%{?dist}
Summary:        An example spec

Group:          Development/Libraries
License:        GPLv2+
URL:            http://www.example.dom
Source0:        %{name}-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildArch:      noarch
Requires:       python >= 2.4
BuildRequires:  python-setuptools


%description
An example spec for an rpm.


%prep
%setup -q


%build
%{__python} setup.py build


%install
rm -rf $RPM_BUILD_ROOT
%{__python} setup.py install -O1 --skip-build --root $RPM_BUILD_ROOT/


%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%doc INSTALL LICENSE AUTHORS COPYING
# For noarch packages: sitelib
%{python_sitelib}/*


%changelog
* Wed Jan  7 2009 Steve 'Ashcrow' Milner <smilner+buildbot@redhat.com> - \
1.0.0-1
- example""")
        specfile.flush()
        specfile.seek(0)
        rs = RpmSpec(specfile)
        rs.load()
        self.assertTrue(rs.loaded)
        self.assertEquals(rs.pkg_name, 'example')
        self.assertEquals(rs.pkg_version, '1.0.0')

# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import os
import sys
import shutil
import cStringIO

def nl(s):
    """Convert the given string to the native newline format, assuming it is
    already in normal UNIX newline format (\n).  Use this to create the
    appropriate expectation in a failUnlessEqual"""
    if not isinstance(s, basestring):
        return s
    return s.replace('\n', os.linesep)

class BasedirMixin(object):
    """Mix this in and call setUpBasedir and tearDownBasedir to set up
    a clean basedir with a name given in self.basedir."""

    def setUpBasedir(self):
        self.basedir = "test-basedir"
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

    def tearDownBasedir(self):
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

class PatcherMixin(object):
    """
    Mix this in to get a few special-cased patching methods
    """

    def patch_os_uname(self, replacement):
        # twisted's 'patch' doesn't handle the case where an attribute
        # doesn't exist..
        if hasattr(os, 'uname'):
            self.patch(os, 'uname', replacement)
        else:
            def cleanup():
                del os.uname
            self.addCleanup(cleanup)
            os.uname = replacement

class StdoutAssertionsMixin(object):
    """
    Mix this in to be able to assert on stdout during the test
    """
    def setUpStdoutAssertions(self):
        self.stdout = cStringIO.StringIO()
        self.patch(sys, 'stdout', self.stdout)

    def assertWasQuiet(self):
        self.assertEqual(self.stdout.getvalue(), '')

    def assertInStdout(self, exp):
        self.assertIn(exp, self.stdout.getvalue())

    def assertStdoutEqual(self, exp, msg=None):
        self.assertEqual(exp, self.stdout.getvalue(), msg)

    def getStdout(self):
        return self.stdout.getvalue().strip()

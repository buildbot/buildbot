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
import mock
from twisted.trial import unittest
from buildslave.scripts import create_slave
from buildslave.test.util import misc


class TestMakeBaseDir(misc.StdoutAssertionsMixin, unittest.TestCase):
    """
    Test buildslave.scripts.create_slave._makeBaseDir()
    """
    def setUp(self):
        # capture stdout
        self.setUpStdoutAssertions()

        # patch os.mkdir() to do nothing
        self.mkdir = mock.Mock()
        self.patch(os, "mkdir", self.mkdir)

    def testBasedirExists(self):
        """
        test calling _makeBaseDir() on existing base directory
        """
        self.patch(os.path, "exists", mock.Mock(return_value=True))

        # call _makeBaseDir()
        create_slave._makeBaseDir("dummy", False)

        # check that correct message was printed to stdout
        self.assertStdoutEqual("updating existing installation\n")
        # check that os.mkdir was not called
        self.assertFalse(self.mkdir.called,
                         "unexpected call to os.mkdir()")

    def testBasedirExistsQuiet(self):
        """
        test calling _makeBaseDir() on existing base directory with
        quiet flag enabled
        """
        self.patch(os.path, "exists", mock.Mock(return_value=True))

        # call _makeBaseDir()
        create_slave._makeBaseDir("dummy", True)

        # check that nothing was printed to stdout
        self.assertWasQuiet()
        # check that os.mkdir was not called
        self.assertFalse(self.mkdir.called,
                         "unexpected call to os.mkdir()")

    def testBasedirCreated(self):
        """
        test creating new base directory with _makeBaseDir()
        """
        self.patch(os.path, "exists", mock.Mock(return_value=False))

        # call _makeBaseDir()
        create_slave._makeBaseDir("dummy", False)

        # check that os.mkdir() was called with correct path
        self.mkdir.assert_called_once_with("dummy")
        # check that correct message was printed to stdout
        self.assertStdoutEqual("mkdir dummy\n")

    def testBasedirCreatedQuiet(self):
        """
        test creating new base directory with _makeBaseDir()
        and quiet flag enabled
        """
        self.patch(os.path, "exists", mock.Mock(return_value=False))

        # call _makeBaseDir()
        create_slave._makeBaseDir("dummy", True)

        # check that os.mkdir() was called with correct path
        self.mkdir.assert_called_once_with("dummy")
        # check that nothing was printed to stdout
        self.assertWasQuiet()

    def testMkdirError(self):
        """
        test that _makeBaseDir() handles error creating directory correctly
        """
        self.patch(os.path, "exists", mock.Mock(return_value=False))

        # patch os.mkdir() to raise an exception
        self.patch(os, "mkdir",
                   mock.Mock(side_effect=OSError(0, "dummy-error")))

        # check that correct exception was raised
        self.assertRaisesRegexp(create_slave.CreateSlaveError,
                                "error creating directory dummy: dummy-error",
                                create_slave._makeBaseDir, "dummy", False)


class TestCreateSlave(misc.StdoutAssertionsMixin, unittest.TestCase):
    """
    Test buildslave.scripts.create_slave.createSlave()
    """
    # default options and required arguments
    options = {
               # flags
               "no-logrotate": False,
               "relocatable": False,
               "quiet": False,
               # options
               "basedir": "bdir",
               "allow-shutdown": None,
               "umask": None,
               "usepty": 0,
               "log-size": 16,
               "log-count": 8,
               "keepalive": 4,
               "maxdelay": 2,

               # arguments
               "host": "masterhost",
               "port": 1234,
               "name": "slavename",
               "passwd": "orange"
               }

    def setUp(self):
        # capture stdout
        self.setUpStdoutAssertions()

    def setUpMakeFunctions(self, exception=None):
        """
        patch create_slave._make*() functions with a mocks

        @param exception: if not None, the mocks will raise this exception.
        """
        self._makeBaseDir = mock.Mock(side_effect=exception)
        self.patch(create_slave,
                   "_makeBaseDir",
                   self._makeBaseDir)

        self._makeBuildbotTac = mock.Mock(side_effect=exception)
        self.patch(create_slave,
                   "_makeBuildbotTac",
                   self._makeBuildbotTac)

        self._makeInfoFiles = mock.Mock(side_effect=exception)
        self.patch(create_slave,
                   "_makeInfoFiles",
                   self._makeInfoFiles)

    def assertMakeFunctionsCalls(self, basedir, tac_contents, quiet):
        """
        assert that create_slave._make*() were called with specified arguments
        """
        self._makeBaseDir.assert_called_once_with(basedir, quiet)
        self._makeBuildbotTac.assert_called_once_with(basedir,
                                                      tac_contents,
                                                      quiet)
        self._makeInfoFiles.assert_called_once_with(basedir, quiet)

    def testCreateError(self):
        """
        test that errors while creating buildslave directory are handled
        correctly by createSlave()
        """
        # patch _make*() functions to raise an exception
        self.setUpMakeFunctions(create_slave.CreateSlaveError("err-msg"))

        # call createSlave() and check that we get error exit code
        self.assertEquals(create_slave.createSlave(self.options), 1,
                          "unexpected exit code")

        # check that correct error message was printed on stdout
        self.assertStdoutEqual("err-msg\n"
                               "failed to configure buildslave in bdir\n")

    def testMinArgs(self):
        """
        test calling createSlave() with only required arguments
        """
        # patch _make*() functions to do nothing
        self.setUpMakeFunctions()

        # call createSlave() and check that we get success exit code
        self.assertEquals(create_slave.createSlave(self.options), 0,
                          "unexpected exit code")

        # check _make*() functions were called with correct arguments
        expected_tac_contents = \
            "".join(create_slave.slaveTACTemplate) % self.options
        self.assertMakeFunctionsCalls(self.options["basedir"],
                                      expected_tac_contents,
                                      self.options["quiet"])

        # check that correct info message was printed
        self.assertStdoutEqual("buildslave configured in bdir\n")

    def testNoLogRotate(self):
        """
        test that when --no-logrotate options is used, correct tac file
        is generated.
        """
        options = self.options.copy()
        options["no-logrotate"] = True

        # patch _make*() functions to do nothing
        self.setUpMakeFunctions()

        # call createSlave() and check that we get success exit code
        self.assertEquals(create_slave.createSlave(options), 0,
                          "unexpected exit code")

        # check _make*() functions were called with correct arguments
        expected_tac_contents = (create_slave.slaveTACTemplate[0] +
                                 create_slave.slaveTACTemplate[2]) % options
        self.assertMakeFunctionsCalls(self.options["basedir"],
                                      expected_tac_contents,
                                      self.options["quiet"])

        # check that correct info message was printed
        self.assertStdoutEqual("buildslave configured in bdir\n")

    def testWithOpts(self):
        """
        test calling createSlave() with --relocatable and --allow-shutdown
        options specified.
        """
        options = self.options.copy()
        options["relocatable"] = True
        options["allow-shutdown"] = "signal"

        # patch _make*() functions to do nothing
        self.setUpMakeFunctions()

        # call createSlave() and check that we get success exit code
        self.assertEquals(create_slave.createSlave(options), 0,
                          "unexpected exit code")

        # check _make*() functions were called with correct arguments
        options["allow-shutdown"] = "'signal'"
        expected_tac_contents = \
            "".join(create_slave.slaveTACTemplate) % options
        self.assertMakeFunctionsCalls(self.options["basedir"],
                                      expected_tac_contents,
                                      options["quiet"])

        # check that correct info message was printed
        self.assertStdoutEqual("buildslave configured in bdir\n")

    def testQuiet(self):
        """
        test calling createSlave() with --quiet flag
        """
        options = self.options.copy()
        options["quiet"] = True

        # patch _make*() functions to do nothing
        self.setUpMakeFunctions()

        # call createSlave() and check that we get success exit code
        self.assertEquals(create_slave.createSlave(options), 0,
                          "unexpected exit code")

        # check _make*() functions were called with correct arguments
        expected_tac_contents = \
            "".join(create_slave.slaveTACTemplate) % options
        self.assertMakeFunctionsCalls(options["basedir"],
                                      expected_tac_contents,
                                      options["quiet"])

        # there should be no output on stdout
        self.assertWasQuiet()

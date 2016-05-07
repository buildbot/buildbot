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
import re

import mock
from twisted.trial import unittest

from buildslave.scripts import create_slave
from buildslave.test.util import misc


def _regexp_path(name, *names):
    """
    Join two or more path components and create a regexp that will match that
    path.
    """
    return os.path.join(name, *names).replace("\\", "\\\\")


class TestMakeBaseDir(misc.LoggingMixin, unittest.TestCase):

    """
    Test buildslave.scripts.create_slave._makeBaseDir()
    """

    def setUp(self):
        # capture stdout
        self.setUpLogging()

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

        # check that correct message was printed to the log
        self.assertLogged("updating existing installation")
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
        # check that correct message was printed to the log
        self.assertLogged("mkdir dummy")

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


class TestMakeBuildbotTac(misc.LoggingMixin,
                          misc.FileIOMixin,
                          unittest.TestCase):

    """
    Test buildslave.scripts.create_slave._makeBuildbotTac()
    """

    def setUp(self):
        # capture stdout
        self.setUpLogging()

        # patch os.chmod() to do nothing
        self.chmod = mock.Mock()
        self.patch(os, "chmod", self.chmod)

        # generate OS specific relative path to buildbot.tac inside basedir
        self.tac_file_path = _regexp_path("bdir", "buildbot.tac")

    def testTacOpenError(self):
        """
        test that _makeBuildbotTac() handles open() errors on buildbot.tac
        """
        self.patch(os.path, "exists", mock.Mock(return_value=True))
        # patch open() to raise exception
        self.setUpOpenError()

        # call _makeBuildbotTac() and check that correct exception is raised
        expected_message = "error reading %s: dummy-msg" % self.tac_file_path
        self.assertRaisesRegexp(create_slave.CreateSlaveError,
                                expected_message,
                                create_slave._makeBuildbotTac,
                                "bdir", "contents", False)

    def testTacReadError(self):
        """
        test that _makeBuildbotTac() handles read() errors on buildbot.tac
        """
        self.patch(os.path, "exists", mock.Mock(return_value=True))
        # patch read() to raise exception
        self.setUpReadError()

        # call _makeBuildbotTac() and check that correct exception is raised
        expected_message = "error reading %s: dummy-msg" % self.tac_file_path
        self.assertRaisesRegexp(create_slave.CreateSlaveError,
                                expected_message,
                                create_slave._makeBuildbotTac,
                                "bdir", "contents", False)

    def testTacWriteError(self):
        """
        test that _makeBuildbotTac() handles write() errors on buildbot.tac
        """
        self.patch(os.path, "exists", mock.Mock(return_value=False))
        # patch write() to raise exception
        self.setUpWriteError(0)

        # call _makeBuildbotTac() and check that correct exception is raised
        expected_message = "could not write %s: dummy-msg" % self.tac_file_path
        self.assertRaisesRegexp(create_slave.CreateSlaveError,
                                expected_message,
                                create_slave._makeBuildbotTac,
                                "bdir", "contents", False)

    def checkTacFileCorrect(self, quiet):
        """
        Utility function to test calling _makeBuildbotTac() on base directory
        with existing buildbot.tac file, which does not need to be changed.

        @param quiet: the value of 'quiet' argument for _makeBuildbotTac()
        """
        # set-up mocks to simulate buildbot.tac file in the basedir
        self.patch(os.path, "exists", mock.Mock(return_value=True))
        self.setUpOpen("test-tac-contents")

        # call _makeBuildbotTac()
        create_slave._makeBuildbotTac("bdir", "test-tac-contents", quiet)

        # check that write() was not called
        self.assertFalse(self.fileobj.write.called,
                         "unexpected write() call")

        # check output to the log
        if quiet:
            self.assertWasQuiet()
        else:
            self.assertLogged(
                "buildbot.tac already exists and is correct")

    def testTacFileCorrect(self):
        """
        call _makeBuildbotTac() on base directory which contains a buildbot.tac
        file, which does not need to be changed
        """
        self.checkTacFileCorrect(False)

    def testTacFileCorrectQuiet(self):
        """
        call _makeBuildbotTac() on base directory which contains a buildbot.tac
        file, which does not need to be changed. Check that quite flag works
        """
        self.checkTacFileCorrect(True)

    def checkDiffTacFile(self, quiet):
        """
        Utility function to test calling _makeBuildbotTac() on base directory
        with a buildbot.tac file, with does needs to be changed.

        @param quiet: the value of 'quiet' argument for _makeBuildbotTac()
        """
        # set-up mocks to simulate buildbot.tac file in basedir
        self.patch(os.path, "exists", mock.Mock(return_value=True))
        self.setUpOpen("old-tac-contents")

        # call _makeBuildbotTac()
        create_slave._makeBuildbotTac("bdir", "new-tac-contents", quiet)

        # check that buildbot.tac.new file was created with expected contents
        tac_file_path = os.path.join("bdir", "buildbot.tac")
        self.open.assert_has_calls([mock.call(tac_file_path, "rt"),
                                    mock.call(tac_file_path + ".new", "wt")])
        self.fileobj.write.assert_called_once_with("new-tac-contents")
        self.chmod.assert_called_once_with(tac_file_path + ".new", 0o600)

        # check output to the log
        if quiet:
            self.assertWasQuiet()
        else:
            self.assertLogged("not touching existing buildbot.tac",
                              "creating buildbot.tac.new instead")

    def testDiffTacFile(self):
        """
        call _makeBuildbotTac() on base directory which contains a buildbot.tac
        file, with does needs to be changed.
        """
        self.checkDiffTacFile(False)

    def testDiffTacFileQuiet(self):
        """
        call _makeBuildbotTac() on base directory which contains a buildbot.tac
        file, with does needs to be changed. Check that quite flag works
        """
        self.checkDiffTacFile(True)

    def testNoTacFile(self):
        """
        call _makeBuildbotTac() on base directory with no buildbot.tac file
        """
        self.patch(os.path, "exists", mock.Mock(return_value=False))
        # capture calls to open() and write()
        self.setUpOpen()

        # call _makeBuildbotTac()
        create_slave._makeBuildbotTac("bdir", "test-tac-contents", False)

        # check that buildbot.tac file was created with expected contents
        tac_file_path = os.path.join("bdir", "buildbot.tac")
        self.open.assert_called_once_with(tac_file_path, "wt")
        self.fileobj.write.assert_called_once_with("test-tac-contents")
        self.chmod.assert_called_once_with(tac_file_path, 0o600)


class TestMakeInfoFiles(misc.LoggingMixin,
                        misc.FileIOMixin,
                        unittest.TestCase):

    """
    Test buildslave.scripts.create_slave._makeInfoFiles()
    """

    def setUp(self):
        # capture stdout
        self.setUpLogging()

    def checkMkdirError(self, quiet):
        """
        Utility function to test _makeInfoFiles() when os.mkdir() fails.

        Patch os.mkdir() to raise an exception, and check that _makeInfoFiles()
        handles mkdir errors correctly.

        @param quiet: the value of 'quiet' argument for _makeInfoFiles()
        """
        self.patch(os.path, "exists", mock.Mock(return_value=False))
        # patch os.mkdir() to raise an exception
        self.patch(os, "mkdir", mock.Mock(side_effect=OSError(0, "err-msg")))

        # call _makeInfoFiles() and check that correct exception is raised
        self.assertRaisesRegexp(create_slave.CreateSlaveError,
                                "error creating directory %s: err-msg" %
                                _regexp_path("bdir", "info"),
                                create_slave._makeInfoFiles,
                                "bdir", quiet)

        # check output to the log
        if quiet:
            self.assertWasQuiet()
        else:
            self.assertLogged(
                re.escape("mkdir %s" % os.path.join("bdir", "info")))

    def testMkdirError(self):
        """
        test _makeInfoFiles() when os.mkdir() fails
        """
        self.checkMkdirError(False)

    def testMkdirErrorQuiet(self):
        """
        test _makeInfoFiles() when os.mkdir() fails and quiet flag is enabled
        """
        self.checkMkdirError(True)

    def checkIOError(self, error_type, quiet):
        """
        Utility function to test _makeInfoFiles() when open() or write() fails.

        Patch file IO functions to raise an exception, and check that
        _makeInfoFiles() handles file IO errors correctly.

        @param error_type: type of error to emulate,
                           'open' - patch open() to fail
                           'write' - patch write() to fail
        @param quiet: the value of 'quiet' argument for _makeInfoFiles()
        """
        # patch os.path.exists() to simulate that 'info' directory exists
        # but not 'admin' or 'host' files
        self.patch(os.path, "exists", lambda path: path.endswith("info"))

        # set-up requested IO error
        if error_type == "open":
            self.setUpOpenError(strerror="info-err-msg")
        elif error_type == "write":
            self.setUpWriteError(strerror="info-err-msg")
        else:
            self.fail("unexpected error_type '%s'" % error_type)

        # call _makeInfoFiles() and check that correct exception is raised
        self.assertRaisesRegexp(create_slave.CreateSlaveError,
                                "could not write %s: info-err-msg" %
                                _regexp_path("bdir", "info", "admin"),
                                create_slave._makeInfoFiles,
                                "bdir", quiet)

        # check output to the log
        if quiet:
            self.assertWasQuiet()
        else:
            self.assertLogged(
                re.escape("Creating %s, you need to edit it appropriately." %
                          os.path.join("info", "admin")))

    def testOpenError(self):
        """
        test _makeInfoFiles() when open() fails
        """
        self.checkIOError("open", False)

    def testOpenErrorQuiet(self):
        """
        test _makeInfoFiles() when open() fails and quiet flag is enabled
        """
        self.checkIOError("open", True)

    def testWriteError(self):
        """
        test _makeInfoFiles() when write() fails
        """
        self.checkIOError("write", False)

    def testWriteErrorQuiet(self):
        """
        test _makeInfoFiles() when write() fails and quiet flag is enabled
        """
        self.checkIOError("write", True)

    def checkCreatedSuccessfully(self, quiet):
        """
        Utility function to test _makeInfoFiles() when called on
        base directory that does not have 'info' sub-directory.

        @param quiet: the value of 'quiet' argument for _makeInfoFiles()
        """
        # patch os.path.exists() to report the no dirs/files exists
        self.patch(os.path, "exists", mock.Mock(return_value=False))
        # patch os.mkdir() to do nothing
        mkdir_mock = mock.Mock()
        self.patch(os, "mkdir", mkdir_mock)
        # capture calls to open() and write()
        self.setUpOpen()

        # call _makeInfoFiles()
        create_slave._makeInfoFiles("bdir", quiet)

        # check calls to os.mkdir()
        info_path = os.path.join("bdir", "info")
        mkdir_mock.assert_called_once_with(info_path)

        # check open() calls
        self.open.assert_has_calls(
            [mock.call(os.path.join(info_path, "admin"), "wt"),
             mock.call(os.path.join(info_path, "host"), "wt")])

        # check write() calls
        self.fileobj.write.assert_has_calls(
            [mock.call("Your Name Here <admin@youraddress.invalid>\n"),
             mock.call("Please put a description of this build host here\n")])

        # check output to the log
        if quiet:
            self.assertWasQuiet()
        else:
            self.assertLogged(
                re.escape("mkdir %s" % info_path),
                re.escape("Creating %s, you need to edit it appropriately." %
                          os.path.join("info", "admin")),
                re.escape("Creating %s, you need to edit it appropriately." %
                          os.path.join("info", "host")),
                re.escape("Not creating %s - add it if you wish" %
                          os.path.join("info", "access_ur")),
                re.escape("Please edit the files in %s appropriately." %
                          info_path)
            )

    def testCreatedSuccessfully(self):
        """
        test calling _makeInfoFiles() on basedir without 'info' directory
        """
        self.checkCreatedSuccessfully(False)

    def testCreatedSuccessfullyQuiet(self):
        """
        test calling _makeInfoFiles() on basedir without 'info' directory
        and quiet flag is enabled
        """
        self.checkCreatedSuccessfully(True)

    def testInfoDirExists(self):
        """
        test calling _makeInfoFiles() on basedir with fully populated
        'info' directory
        """
        self.patch(os.path, "exists", mock.Mock(return_value=True))

        create_slave._makeInfoFiles("bdir", False)

        # there should be no messages to stdout
        self.assertWasQuiet()


class TestCreateSlave(misc.LoggingMixin, unittest.TestCase):

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
        "numcpus": None,

        # arguments
        "host": "masterhost",
        "port": 1234,
        "name": "slavename",
        "passwd": "orange"
    }

    def setUp(self):
        # capture stdout
        self.setUpLogging()

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

        # check that correct error message was printed the the log
        self.assertLogged("err-msg",
                          "failed to configure buildslave in bdir")

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

        # check that correct info message was printed to the log
        self.assertLogged("buildslave configured in bdir")

    def assertTACFileContents(self, options):
        """
        Check that TAC file generated with provided options is valid Python
        script and does typical for TAC file logic.
        """

        # import modules for mocking
        import twisted.application.service
        import twisted.python.logfile
        import buildslave.bot

        # mock service.Application class
        application_mock = mock.Mock()
        application_class_mock = mock.Mock(return_value=application_mock)
        self.patch(twisted.application.service, "Application",
                   application_class_mock)

        # mock logging stuff
        logfile_mock = mock.Mock()
        self.patch(twisted.python.logfile.LogFile, "fromFullPath",
                   logfile_mock)

        # mock BuildSlave class
        buildslave_mock = mock.Mock()
        buildslave_class_mock = mock.Mock(return_value=buildslave_mock)
        self.patch(buildslave.bot, "BuildSlave", buildslave_class_mock)

        expected_tac_contents = \
            "".join(create_slave.slaveTACTemplate) % options

        # Executed .tac file with mocked functions with side effect.
        # This will raise exception if .tac file is not valid Python file.
        glb = {}
        exec(expected_tac_contents, glb, glb)

        # only one Application must be created in .tac
        application_class_mock.assert_called_once_with("buildslave")

        # check that BuildSlave created with passed options
        buildslave_class_mock.assert_called_once_with(
            options["host"],
            options["port"],
            options["name"],
            options["passwd"],
            options["basedir"],
            options["keepalive"],
            options["usepty"],
            umask=options["umask"],
            numcpus=options["numcpus"],
            maxdelay=options["maxdelay"],
            allow_shutdown=options["allow-shutdown"])

        # check that BuildSlave instance attached to application
        self.assertEqual(buildslave_mock.method_calls,
                         [mock.call.setServiceParent(application_mock)])

        # .tac file must define global variable "application", instance of
        # Application
        self.assertTrue('application' in glb,
                        ".tac file doesn't define \"application\" variable")
        self.assertTrue(glb['application'] is application_mock,
                        "defined \"application\" variable in .tac file is not "
                        "Application instance")

    def testDefaultTACContents(self):
        """
        test that with default options generated TAC file is valid.
        """

        self.assertTACFileContents(self.options)

    def testBackslashInBasedir(self):
        """
        test that using backslash (typical for Windows platform) in basedir
        won't break generated TAC file.
        """

        p = mock.patch.dict(self.options, {"basedir": r"C:\builslave dir\\"})
        p.start()
        try:
            self.assertTACFileContents(self.options)
        finally:
            p.stop()

    def testQuotesInBasedir(self):
        """
        test that using quotes in basedir won't break generated TAC file.
        """

        p = mock.patch.dict(self.options, {"basedir": r"Buildbot's \"dir"})
        p.start()
        try:
            self.assertTACFileContents(self.options)
        finally:
            p.stop()

    def testDoubleQuotesInBasedir(self):
        """
        test that using double quotes at begin and end of basedir won't break
        generated TAC file.
        """

        p = mock.patch.dict(self.options, {"basedir": r"\"\"Buildbot''"})
        p.start()
        try:
            self.assertTACFileContents(self.options)
        finally:
            p.stop()

    def testSpecialCharactersInOptions(self):
        """
        test that using special characters in options strings won't break
        generated TAC file.
        """

        test_string = ("\"\" & | ^ # @ \\& \\| \\^ \\# \\@ \\n"
                       " \x07 \" \\\" ' \\' ''")
        p = mock.patch.dict(self.options, {
            "basedir": test_string,
            "host": test_string,
            "passwd": test_string,
            "name": test_string,
        })
        p.start()
        try:
            self.assertTACFileContents(self.options)
        finally:
            p.stop()

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

        # check that correct info message was printed to the log
        self.assertLogged("buildslave configured in bdir")

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

        # check that correct info message was printed to the log
        self.assertLogged("buildslave configured in bdir")

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

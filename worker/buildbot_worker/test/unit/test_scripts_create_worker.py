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
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from twisted.trial import unittest

from buildbot_worker.scripts import create_worker
from buildbot_worker.test.util import misc

try:
    from unittest import mock
except ImportError:
    from unittest import mock

if TYPE_CHECKING:
    from typing import Any
    from typing import Literal
    from typing import Mapping

    from buildbot_worker.scripts.base import Options


def _regexp_path(name: str, *names: str) -> str:
    """
    Join two or more path components and create a regexp that will match that
    path.
    """
    return os.path.join(name, *names).replace("\\", "\\\\")


class TestDefaultOptionsMixin:
    # default options and required arguments
    options: Options = {
        # flags
        "no-logrotate": False,
        "relocatable": False,
        "quiet": False,
        "use-tls": False,
        "delete-leftover-dirs": False,
        # options
        "basedir": "bdir",
        "allow-shutdown": None,
        "umask": None,
        "log-size": 16,
        "log-count": 8,
        "keepalive": 4,
        "maxdelay": 2,
        "numcpus": None,
        "protocol": "pb",
        "maxretries": None,
        "connection-string": None,
        "proxy-connection-string": None,
        # arguments
        "host": "masterhost",
        "port": 1234,
        "name": "workername",
        "passwd": "orange",
    }


class TestMakeTAC(TestDefaultOptionsMixin, unittest.TestCase):
    """
    Test buildbot_worker.scripts.create_worker._make_tac()
    """

    def assert_tac_file_contents(
        self,
        tac_contents: str,
        expected_args: Mapping[str, Any],
        relocate: str | None = None,
    ) -> None:
        """
        Check that generated TAC file is a valid Python script and it does what
        is typical for TAC file logic. Mainly create instance of Worker with
        expected arguments.
        """

        # pylint: disable=import-outside-toplevel
        # import modules for mocking
        import twisted.application.service
        import twisted.python.logfile

        import buildbot_worker.bot

        # mock service.Application class
        application_mock = mock.Mock()
        application_class_mock = mock.Mock(return_value=application_mock)
        self.patch(twisted.application.service, "Application", application_class_mock)

        # mock logging stuff
        logfile_mock = mock.Mock()
        self.patch(twisted.python.logfile.LogFile, "fromFullPath", logfile_mock)

        # mock Worker class
        worker_mock = mock.Mock()
        worker_class_mock = mock.Mock(return_value=worker_mock)
        self.patch(buildbot_worker.bot, "Worker", worker_class_mock)

        # Executed .tac file with mocked functions with side effect.
        # This will raise exception if .tac file is not valid Python file.
        globals_dict = {}
        if relocate:
            globals_dict["__file__"] = os.path.join(relocate, "buildbot.tac")
        exec(tac_contents, globals_dict, globals_dict)  # pylint: disable=exec-used

        # only one Application must be created in .tac
        application_class_mock.assert_called_once_with("buildbot-worker")

        # check that Worker created with passed options
        worker_class_mock.assert_called_once_with(
            expected_args["host"],
            expected_args["port"],
            expected_args["name"],
            expected_args["passwd"],
            expected_args["basedir"],
            expected_args["keepalive"],
            umask=expected_args["umask"],
            numcpus=expected_args["numcpus"],
            protocol=expected_args["protocol"],
            maxdelay=expected_args["maxdelay"],
            allow_shutdown=expected_args["allow-shutdown"],
            maxRetries=expected_args["maxretries"],
            useTls=expected_args["use-tls"],
            delete_leftover_dirs=expected_args["delete-leftover-dirs"],
            connection_string=expected_args["connection-string"],
            proxy_connection_string=expected_args["proxy-connection-string"],
        )

        # check that Worker instance attached to application
        self.assertEqual(worker_mock.method_calls, [mock.call.setServiceParent(application_mock)])

        # .tac file must define global variable "application", instance of
        # Application
        self.assertTrue(
            'application' in globals_dict, ".tac file doesn't define \"application\" variable"
        )
        self.assertTrue(
            globals_dict['application'] is application_mock,
            "defined \"application\" variable in .tac file is not Application instance",
        )

    def test_default_tac_contents(self) -> None:
        """
        test that with default options generated TAC file is valid.
        """
        tac_contents = create_worker._make_tac(self.options.copy())

        self.assert_tac_file_contents(tac_contents, self.options)

    def test_backslash_in_basedir(self) -> None:
        """
        test that using backslash (typical for Windows platform) in basedir
        won't break generated TAC file.
        """
        options = self.options.copy()
        options["basedir"] = r"C:\buildbot-worker dir\\"

        tac_contents = create_worker._make_tac(options.copy())

        self.assert_tac_file_contents(tac_contents, options)

    def test_quotes_in_basedir(self) -> None:
        """
        test that using quotes in basedir won't break generated TAC file.
        """
        options = self.options.copy()
        options["basedir"] = r"Buildbot's \"dir"

        tac_contents = create_worker._make_tac(options.copy())

        self.assert_tac_file_contents(tac_contents, options)

    def test_double_quotes_in_basedir(self) -> None:
        """
        test that using double quotes at begin and end of basedir won't break
        generated TAC file.
        """
        options = self.options.copy()
        options["basedir"] = r"\"\"Buildbot''"

        tac_contents = create_worker._make_tac(options.copy())

        self.assert_tac_file_contents(tac_contents, options)

    def test_special_characters_in_options(self) -> None:
        """
        test that using special characters in options strings won't break
        generated TAC file.
        """
        test_string = "\"\" & | ^ # @ \\& \\| \\^ \\# \\@ \\n \x07 \" \\\" ' \\' ''"
        options = self.options.copy()
        options["basedir"] = test_string
        options["host"] = test_string
        options["passwd"] = test_string
        options["name"] = test_string

        tac_contents = create_worker._make_tac(options.copy())

        self.assert_tac_file_contents(tac_contents, options)

    def test_flags_with_non_default_values(self) -> None:
        """
        test that flags with non-default values will be correctly written to
        generated TAC file.
        """
        options = self.options.copy()
        options["quiet"] = True
        options["use-tls"] = True
        options["delete-leftover-dirs"] = True

        tac_contents = create_worker._make_tac(options.copy())

        self.assert_tac_file_contents(tac_contents, options)

    def test_log_rotate(self) -> None:
        """
        test that when --no-logrotate options is not used, correct tac file
        is generated.
        """
        options = self.options.copy()
        options["no-logrotate"] = False

        tac_contents = create_worker._make_tac(options.copy())

        self.assertIn("from twisted.python.logfile import LogFile", tac_contents)
        self.assert_tac_file_contents(tac_contents, options)

    def test_no_log_rotate(self) -> None:
        """
        test that when --no-logrotate options is used, correct tac file
        is generated.
        """
        options = self.options.copy()
        options["no-logrotate"] = True

        tac_contents = create_worker._make_tac(options.copy())

        self.assertNotIn("from twisted.python.logfile import LogFile", tac_contents)
        self.assert_tac_file_contents(tac_contents, options)

    def test_relocatable_true(self) -> None:
        """
        test that when --relocatable option is True, worker is created from
        generated TAC file with correct basedir argument before and after
        relocation.
        """
        options = self.options.copy()
        options["relocatable"] = True
        options["basedir"] = os.path.join(os.getcwd(), "worker1")

        tac_contents = create_worker._make_tac(options.copy())

        self.assert_tac_file_contents(tac_contents, options, relocate=options["basedir"])

        _relocate = os.path.join(os.getcwd(), "worker2")
        options["basedir"] = _relocate
        self.assert_tac_file_contents(tac_contents, options, relocate=_relocate)

    def test_relocatable_false(self) -> None:
        """
        test that when --relocatable option is False, worker is created from
        generated TAC file with the same basedir argument before and after
        relocation.
        """
        options = self.options.copy()
        options["relocatable"] = False
        options["basedir"] = os.path.join(os.getcwd(), "worker1")

        tac_contents = create_worker._make_tac(options.copy())

        self.assert_tac_file_contents(tac_contents, options, relocate=options["basedir"])

        _relocate = os.path.join(os.getcwd(), "worker2")
        self.assert_tac_file_contents(tac_contents, options, relocate=_relocate)

    def test_options_with_non_default_values(self) -> None:
        """
        test that options with non-default values will be correctly written to
        generated TAC file and used as argument of Worker.
        """
        options = self.options.copy()
        options["allow-shutdown"] = "signal"
        options["umask"] = "18"
        options["log-size"] = 160
        options["log-count"] = "80"
        options["keepalive"] = 40
        options["maxdelay"] = 20
        options["numcpus"] = "10"
        options["protocol"] = "null"
        options["maxretries"] = "1"
        options["proxy-connection-string"] = "TCP:proxy.com:8080"

        tac_contents = create_worker._make_tac(options.copy())

        # These values are expected to be used as non-string literals in
        # generated TAC file.
        self.assertIn("rotateLength = 160", tac_contents)
        self.assertIn("maxRotatedFiles = 80", tac_contents)
        self.assertIn("keepalive = 40", tac_contents)
        self.assertIn("maxdelay = 20", tac_contents)
        self.assertIn("umask = 18", tac_contents)
        self.assertIn("numcpus = 10", tac_contents)
        self.assertIn("maxretries = 1", tac_contents)

        # Check also as arguments used in Worker initialization.
        options["umask"] = 18
        options["numcpus"] = 10
        options["maxretries"] = 1
        self.assert_tac_file_contents(tac_contents, options)

    def test_umask_octal_value(self) -> None:
        """
        test that option umask with octal value will be correctly written to
        generated TAC file and used as argument of Worker.
        """
        options = self.options.copy()
        options["umask"] = "0o22"

        tac_contents = create_worker._make_tac(options.copy())

        self.assertIn("umask = 0o22", tac_contents)
        options["umask"] = 18
        self.assert_tac_file_contents(tac_contents, options)

    def test_connection_string(self) -> None:
        """
        test that when --connection-string options is used, correct tac file
        is generated.
        """
        options = self.options.copy()
        options["connection-string"] = "TLS:buildbot-master.com:9989"

        tac_contents = create_worker._make_tac(options.copy())

        options["host"] = None
        options["port"] = None
        self.assert_tac_file_contents(tac_contents, options)


class TestMakeBaseDir(misc.StdoutAssertionsMixin, unittest.TestCase):
    """
    Test buildbot_worker.scripts.create_worker._makeBaseDir()
    """

    def setUp(self) -> None:
        # capture stdout
        self.setUpStdoutAssertions()

        # patch os.mkdir() to do nothing
        self.mkdir = mock.Mock()
        self.patch(os, "mkdir", self.mkdir)

    def testBasedirExists(self) -> None:
        """
        test calling _makeBaseDir() on existing base directory
        """
        self.patch(os.path, "exists", mock.Mock(return_value=True))

        # call _makeBaseDir()
        create_worker._makeBaseDir("dummy", False)

        # check that correct message was printed to stdout
        self.assertStdoutEqual("updating existing installation\n")
        # check that os.mkdir was not called
        self.assertFalse(self.mkdir.called, "unexpected call to os.mkdir()")

    def testBasedirExistsQuiet(self) -> None:
        """
        test calling _makeBaseDir() on existing base directory with
        quiet flag enabled
        """
        self.patch(os.path, "exists", mock.Mock(return_value=True))

        # call _makeBaseDir()
        create_worker._makeBaseDir("dummy", True)

        # check that nothing was printed to stdout
        self.assertWasQuiet()
        # check that os.mkdir was not called
        self.assertFalse(self.mkdir.called, "unexpected call to os.mkdir()")

    def testBasedirCreated(self) -> None:
        """
        test creating new base directory with _makeBaseDir()
        """
        self.patch(os.path, "exists", mock.Mock(return_value=False))

        # call _makeBaseDir()
        create_worker._makeBaseDir("dummy", False)

        # check that os.mkdir() was called with correct path
        self.mkdir.assert_called_once_with("dummy")
        # check that correct message was printed to stdout
        self.assertStdoutEqual("mkdir dummy\n")

    def testBasedirCreatedQuiet(self) -> None:
        """
        test creating new base directory with _makeBaseDir()
        and quiet flag enabled
        """
        self.patch(os.path, "exists", mock.Mock(return_value=False))

        # call _makeBaseDir()
        create_worker._makeBaseDir("dummy", True)

        # check that os.mkdir() was called with correct path
        self.mkdir.assert_called_once_with("dummy")
        # check that nothing was printed to stdout
        self.assertWasQuiet()

    def testMkdirError(self) -> None:
        """
        test that _makeBaseDir() handles error creating directory correctly
        """
        self.patch(os.path, "exists", mock.Mock(return_value=False))

        # patch os.mkdir() to raise an exception
        self.patch(os, "mkdir", mock.Mock(side_effect=OSError(0, "dummy-error")))

        # check that correct exception was raised
        with self.assertRaisesRegex(
            create_worker.CreateWorkerError, "error creating directory dummy"
        ):
            create_worker._makeBaseDir("dummy", False)


class TestMakeBuildbotTac(misc.StdoutAssertionsMixin, misc.FileIOMixin, unittest.TestCase):
    """
    Test buildbot_worker.scripts.create_worker._makeBuildbotTac()
    """

    def setUp(self) -> None:
        # capture stdout
        self.setUpStdoutAssertions()

        # patch os.chmod() to do nothing
        self.chmod = mock.Mock()
        self.patch(os, "chmod", self.chmod)

        # generate OS specific relative path to buildbot.tac inside basedir
        self.tac_file_path = _regexp_path("bdir", "buildbot.tac")

    def testTacOpenError(self) -> None:
        """
        test that _makeBuildbotTac() handles open() errors on buildbot.tac
        """
        self.patch(os.path, "exists", mock.Mock(return_value=True))
        # patch open() to raise exception
        self.setUpOpenError()

        # call _makeBuildbotTac() and check that correct exception is raised
        expected_message = f"error reading {self.tac_file_path}"
        with self.assertRaisesRegex(create_worker.CreateWorkerError, expected_message):
            create_worker._makeBuildbotTac("bdir", "contents", False)

    def testTacReadError(self) -> None:
        """
        test that _makeBuildbotTac() handles read() errors on buildbot.tac
        """
        self.patch(os.path, "exists", mock.Mock(return_value=True))
        # patch read() to raise exception
        self.setUpReadError()

        # call _makeBuildbotTac() and check that correct exception is raised
        expected_message = f"error reading {self.tac_file_path}"
        with self.assertRaisesRegex(create_worker.CreateWorkerError, expected_message):
            create_worker._makeBuildbotTac("bdir", "contents", False)

    def testTacWriteError(self) -> None:
        """
        test that _makeBuildbotTac() handles write() errors on buildbot.tac
        """
        self.patch(os.path, "exists", mock.Mock(return_value=False))
        # patch write() to raise exception
        self.setUpWriteError(0)

        # call _makeBuildbotTac() and check that correct exception is raised
        expected_message = f"could not write {self.tac_file_path}"
        with self.assertRaisesRegex(create_worker.CreateWorkerError, expected_message):
            create_worker._makeBuildbotTac("bdir", "contents", False)

    def checkTacFileCorrect(self, quiet: bool) -> None:
        """
        Utility function to test calling _makeBuildbotTac() on base directory
        with existing buildbot.tac file, which does not need to be changed.

        @param quiet: the value of 'quiet' argument for _makeBuildbotTac()
        """
        # set-up mocks to simulate buildbot.tac file in the basedir
        self.patch(os.path, "exists", mock.Mock(return_value=True))
        self.setUpOpen("test-tac-contents")

        # call _makeBuildbotTac()
        create_worker._makeBuildbotTac("bdir", "test-tac-contents", quiet)

        # check that write() was not called
        self.assertFalse(self.fileobj.write.called, "unexpected write() call")

        # check output to stdout
        if quiet:
            self.assertWasQuiet()
        else:
            self.assertStdoutEqual("buildbot.tac already exists and is correct\n")

    def testTacFileCorrect(self) -> None:
        """
        call _makeBuildbotTac() on base directory which contains a buildbot.tac
        file, which does not need to be changed
        """
        self.checkTacFileCorrect(False)

    def testTacFileCorrectQuiet(self) -> None:
        """
        call _makeBuildbotTac() on base directory which contains a buildbot.tac
        file, which does not need to be changed. Check that quite flag works
        """
        self.checkTacFileCorrect(True)

    def checkDiffTacFile(self, quiet: bool) -> None:
        """
        Utility function to test calling _makeBuildbotTac() on base directory
        with a buildbot.tac file, with does needs to be changed.

        @param quiet: the value of 'quiet' argument for _makeBuildbotTac()
        """
        # set-up mocks to simulate buildbot.tac file in basedir
        self.patch(os.path, "exists", mock.Mock(return_value=True))
        self.setUpOpen("old-tac-contents")

        # call _makeBuildbotTac()
        create_worker._makeBuildbotTac("bdir", "new-tac-contents", quiet)

        # check that buildbot.tac.new file was created with expected contents
        tac_file_path = os.path.join("bdir", "buildbot.tac")
        self.open.assert_has_calls([
            mock.call(tac_file_path),
            mock.call(tac_file_path + ".new", "w"),
        ])
        self.fileobj.write.assert_called_once_with("new-tac-contents")
        self.chmod.assert_called_once_with(tac_file_path + ".new", 0o600)

        # check output to stdout
        if quiet:
            self.assertWasQuiet()
        else:
            self.assertStdoutEqual(
                "not touching existing buildbot.tac\ncreating buildbot.tac.new instead\n"
            )

    def testDiffTacFile(self) -> None:
        """
        call _makeBuildbotTac() on base directory which contains a buildbot.tac
        file, with does needs to be changed.
        """
        self.checkDiffTacFile(False)

    def testDiffTacFileQuiet(self) -> None:
        """
        call _makeBuildbotTac() on base directory which contains a buildbot.tac
        file, with does needs to be changed. Check that quite flag works
        """
        self.checkDiffTacFile(True)

    def testNoTacFile(self) -> None:
        """
        call _makeBuildbotTac() on base directory with no buildbot.tac file
        """
        self.patch(os.path, "exists", mock.Mock(return_value=False))
        # capture calls to open() and write()
        self.setUpOpen()

        # call _makeBuildbotTac()
        create_worker._makeBuildbotTac("bdir", "test-tac-contents", False)

        # check that buildbot.tac file was created with expected contents
        tac_file_path = os.path.join("bdir", "buildbot.tac")
        self.open.assert_called_once_with(tac_file_path, "w")
        self.fileobj.write.assert_called_once_with("test-tac-contents")
        self.chmod.assert_called_once_with(tac_file_path, 0o600)


class TestMakeInfoFiles(misc.StdoutAssertionsMixin, misc.FileIOMixin, unittest.TestCase):
    """
    Test buildbot_worker.scripts.create_worker._makeInfoFiles()
    """

    def setUp(self) -> None:
        # capture stdout
        self.setUpStdoutAssertions()

    def checkMkdirError(self, quiet: bool) -> None:
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
        with self.assertRaisesRegex(
            create_worker.CreateWorkerError,
            "error creating directory {}".format(_regexp_path("bdir", "info")),
        ):
            create_worker._makeInfoFiles("bdir", quiet)

        # check output to stdout
        if quiet:
            self.assertWasQuiet()
        else:
            self.assertStdoutEqual("mkdir {}\n".format(os.path.join("bdir", "info")))

    def testMkdirError(self) -> None:
        """
        test _makeInfoFiles() when os.mkdir() fails
        """
        self.checkMkdirError(False)

    def testMkdirErrorQuiet(self) -> None:
        """
        test _makeInfoFiles() when os.mkdir() fails and quiet flag is enabled
        """
        self.checkMkdirError(True)

    def checkIOError(self, error_type: Literal["open", "write"], quiet: bool) -> None:
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
            self.setUpOpenError()
        elif error_type == "write":
            self.setUpWriteError()
        else:
            self.fail(f"unexpected error_type '{error_type}'")

        # call _makeInfoFiles() and check that correct exception is raised
        with self.assertRaisesRegex(
            create_worker.CreateWorkerError,
            "could not write {}".format(_regexp_path("bdir", "info", "admin")),
        ):
            create_worker._makeInfoFiles("bdir", quiet)

        # check output to stdout
        if quiet:
            self.assertWasQuiet()
        else:
            self.assertStdoutEqual(
                "Creating {}, you need to edit it appropriately.\n".format(
                    os.path.join("info", "admin")
                )
            )

    def testOpenError(self) -> None:
        """
        test _makeInfoFiles() when open() fails
        """
        self.checkIOError("open", False)

    def testOpenErrorQuiet(self) -> None:
        """
        test _makeInfoFiles() when open() fails and quiet flag is enabled
        """
        self.checkIOError("open", True)

    def testWriteError(self) -> None:
        """
        test _makeInfoFiles() when write() fails
        """
        self.checkIOError("write", False)

    def testWriteErrorQuiet(self) -> None:
        """
        test _makeInfoFiles() when write() fails and quiet flag is enabled
        """
        self.checkIOError("write", True)

    def checkCreatedSuccessfully(self, quiet: bool) -> None:
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
        create_worker._makeInfoFiles("bdir", quiet)

        # check calls to os.mkdir()
        info_path = os.path.join("bdir", "info")
        mkdir_mock.assert_called_once_with(info_path)

        # check open() calls
        self.open.assert_has_calls([
            mock.call(os.path.join(info_path, "admin"), "w"),
            mock.call(os.path.join(info_path, "host"), "w"),
        ])

        # check write() calls
        self.fileobj.write.assert_has_calls([
            mock.call("Your Name Here <admin@youraddress.invalid>\n"),
            mock.call("Please put a description of this build host here\n"),
        ])

        # check output to stdout
        if quiet:
            self.assertWasQuiet()
        else:
            self.assertStdoutEqual(
                (
                    "mkdir {}\n"
                    "Creating {}, you need to edit it appropriately.\n"
                    "Creating {}, you need to edit it appropriately.\n"
                    "Not creating {} - add it if you wish\n"
                    "Please edit the files in {} appropriately.\n"
                ).format(
                    info_path,
                    os.path.join("info", "admin"),
                    os.path.join("info", "host"),
                    os.path.join("info", "access_uri"),
                    info_path,
                )
            )

    def testCreatedSuccessfully(self) -> None:
        """
        test calling _makeInfoFiles() on basedir without 'info' directory
        """
        self.checkCreatedSuccessfully(False)

    def testCreatedSuccessfullyQuiet(self) -> None:
        """
        test calling _makeInfoFiles() on basedir without 'info' directory
        and quiet flag is enabled
        """
        self.checkCreatedSuccessfully(True)

    def testInfoDirExists(self) -> None:
        """
        test calling _makeInfoFiles() on basedir with fully populated
        'info' directory
        """
        self.patch(os.path, "exists", mock.Mock(return_value=True))

        create_worker._makeInfoFiles("bdir", False)

        # there should be no messages to stdout
        self.assertWasQuiet()


class TestCreateWorker(misc.StdoutAssertionsMixin, TestDefaultOptionsMixin, unittest.TestCase):
    """
    Test buildbot_worker.scripts.create_worker.createWorker()
    """

    def setUp(self) -> None:
        # capture stdout
        self.setUpStdoutAssertions()

    def setUpMakeFunctions(self, exception: BaseException | None = None) -> None:
        """
        patch create_worker._make*() functions with a mocks

        @param exception: if not None, the mocks will raise this exception.
        """
        self._makeBaseDir = mock.Mock(side_effect=exception)
        self.patch(create_worker, "_makeBaseDir", self._makeBaseDir)

        self._makeBuildbotTac = mock.Mock(side_effect=exception)
        self.patch(create_worker, "_makeBuildbotTac", self._makeBuildbotTac)

        self._makeInfoFiles = mock.Mock(side_effect=exception)
        self.patch(create_worker, "_makeInfoFiles", self._makeInfoFiles)

    def assertMakeFunctionsCalls(self, basedir: str, tac_contents: str, quiet: bool) -> None:
        """
        assert that create_worker._make*() were called with specified arguments
        """
        self._makeBaseDir.assert_called_once_with(basedir, quiet)
        self._makeBuildbotTac.assert_called_once_with(basedir, tac_contents, quiet)
        self._makeInfoFiles.assert_called_once_with(basedir, quiet)

    def testCreateError(self) -> None:
        """
        test that errors while creating worker directory are handled
        correctly by createWorker()
        """
        # patch _make*() functions to raise an exception
        self.setUpMakeFunctions(create_worker.CreateWorkerError("err-msg"))

        # call createWorker() and check that we get error exit code
        self.assertEqual(create_worker.createWorker(self.options), 1, "unexpected exit code")

        # check that correct error message was printed on stdout
        self.assertStdoutEqual("err-msg\nfailed to configure worker in bdir\n")

    def testMinArgs(self) -> None:
        """
        test calling createWorker() with only required arguments
        """
        # patch _make*() functions to do nothing
        self.setUpMakeFunctions()

        # call createWorker() and check that we get success exit code
        self.assertEqual(create_worker.createWorker(self.options), 0, "unexpected exit code")

        # check _make*() functions were called with correct arguments
        expected_tac_contents = create_worker._make_tac(self.options.copy())
        self.assertMakeFunctionsCalls(
            self.options["basedir"], expected_tac_contents, self.options["quiet"]
        )

        # check that correct info message was printed
        self.assertStdoutEqual("worker configured in bdir\n")

    def testQuiet(self) -> None:
        """
        test calling createWorker() with --quiet flag
        """
        options = self.options.copy()
        options["quiet"] = True

        # patch _make*() functions to do nothing
        self.setUpMakeFunctions()

        # call createWorker() and check that we get success exit code
        self.assertEqual(create_worker.createWorker(options), 0, "unexpected exit code")

        # check _make*() functions were called with correct arguments
        expected_tac_contents = create_worker._make_tac(self.options)
        self.assertMakeFunctionsCalls(options["basedir"], expected_tac_contents, options["quiet"])

        # there should be no output on stdout
        self.assertWasQuiet()

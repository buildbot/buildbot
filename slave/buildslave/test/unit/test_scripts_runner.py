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
import time
import mock
import errno
import signal
from twisted.trial import unittest
from twisted.python import usage
from buildslave.scripts import runner, startup
from buildslave.test.util import misc


class TestStopSlave(misc.OpenFileMixin,
                    misc.StdoutAssertionsMixin,
                    unittest.TestCase):
    """
    Test buildslave.scripts.runner.stopSlave()
    """
    PID = 9876
    def setUp(self):
        self.setUpStdoutAssertions()

        # patch os.chdir() to do nothing
        self.patch(os, "chdir", mock.Mock())

    def test_no_pid_file(self):
        """
        test calling stopSlave() when no pid file is present
        """

        # patch open() to raise 'file not found' exception
        self.setUpOpenError(2)

        # check that stop() raises SlaveNotRunning exception
        self.assertRaises(runner.SlaveNotRunning,
                          runner.stopSlave, None, False)

    def test_successful_stop(self):
        """
        test stopSlave() on a successful slave stop
        """

        def emulated_kill(pid, sig):
            if sig == 0:
                # when probed if a signal can be send to the process
                # emulate that it is dead with 'No such process' error
                raise OSError(errno.ESRCH, "dummy")

        # patch open() to return a pid file
        self.setUpOpen(str(self.PID))

        # patch os.kill to emulate successful kill
        mocked_kill = mock.Mock(side_effect=emulated_kill)
        self.patch(os, "kill", mocked_kill)

        # don't waste time
        self.patch(time, "sleep", mock.Mock())

        # check that stopSlave() sends expected signal to right PID
        # and print correct message to stdout
        runner.stopSlave(None, False)
        mocked_kill.assert_has_calls([mock.call(self.PID, signal.SIGTERM),
                                      mock.call(self.PID, 0)])
        self.assertStdoutEqual("buildslave process %s is dead\n" % self.PID)


class TestStop(misc.IsBuildslaveDirMixin,
               misc.StdoutAssertionsMixin,
               unittest.TestCase):
    """
    Test buildslave.scripts.runner.stop()
    """
    config = {"basedir": "dummy", "quiet": False}

    def setUp(self):
        # patch basedir check to always succeed
        self.setupUpIsBuildslaveDir(True)

    def test_no_slave_running(self):
        """
        test calling stop() when no slave is running
        """
        self.setUpStdoutAssertions()

        # patch stopSlave() to raise an exception
        mock_stopSlave = mock.Mock(side_effect=runner.SlaveNotRunning())
        self.patch(runner, "stopSlave", mock_stopSlave)

        runner.stop(self.config)
        self.assertStdoutEqual("buildslave not running\n")

    def test_successful_stop(self):
        """
        test calling stop() when slave is running
        """
        # patch stopSlave() to do nothing
        mock_stopSlave = mock.Mock()
        self.patch(runner, "stopSlave", mock_stopSlave)

        runner.stop(self.config)
        mock_stopSlave.assert_called_once_with(self.config["basedir"],
                                               self.config["quiet"],
                                               "TERM")


class TestRestart(misc.IsBuildslaveDirMixin,
                  misc.StdoutAssertionsMixin,
                  unittest.TestCase):
    """
    Test buildslave.scripts.runner.restart()
    """
    config = {"basedir": "dummy", "nodaemon": False, "quiet": False}

    def setUp(self):
        self.setUpStdoutAssertions()

        # patch basedir check to always succeed
        self.setupUpIsBuildslaveDir(True)

        # patch startup.startSlave() to do nothing
        self.startSlave = mock.Mock()
        self.patch(startup, "startSlave", self.startSlave)

    def test_no_slave_running(self):
        """
        test calling restart() when no slave is running
        """
        # patch stopSlave() to raise an exception
        mock_stopSlave = mock.Mock(side_effect=runner.SlaveNotRunning())
        self.patch(runner, "stopSlave", mock_stopSlave)

        # check that restart() calls startSlave() and prints correct messages
        runner.restart(self.config)
        self.startSlave.assert_called_once_with(self.config["basedir"],
                                                self.config["quiet"],
                                                self.config["nodaemon"]);
        self.assertStdoutEqual("no old buildslave process found to stop\n"
                               "now restarting buildslave process..\n")


    def test_restart(self):
        """
        test calling restart() when slave is running
        """
        # patch stopSlave() to do nothing
        mock_stopSlave = mock.Mock()
        self.patch(runner, "stopSlave", mock_stopSlave)

        # check that restart() calls startSlave() and prints correct messages
        runner.restart(self.config)
        self.startSlave.assert_called_once_with(self.config["basedir"],
                                                self.config["quiet"],
                                                self.config["nodaemon"]);
        self.assertStdoutEqual("now restarting buildslave process..\n")


class TestUpgradeSlave(misc.IsBuildslaveDirMixin, unittest.TestCase):
    """
    Test buildslave.scripts.runner.upgradeSlave()
    """

    def test_upgradeSlave_bad_basedir(self):
        """
        test calling upgradeSlave() with bad base directory
        """
        # override isBuildslaveDir() to always fail
        self.setupUpIsBuildslaveDir(False)

        # call upgradeSlave() and check that correct exit code is returned
        config = {"basedir" : "dummy"}
        self.assertEqual(runner.upgradeSlave(config), 1,
                         "unexpected exit code")

        # check that isBuildslaveDir was called with correct argument
        self.isBuildslaveDir.assert_called_once_with("dummy")

class OptionsMixin(object):
    def assertOptions(self, opts, exp):
        got = dict([(k, opts[k]) for k in exp])
        if got != exp:
            msg = []
            for k in exp:
                if opts[k] != exp[k]:
                    msg.append(" %s: expected %r, got %r" %
                               (k, exp[k], opts[k]))
            self.fail("did not get expected options\n" + ("\n".join(msg)))


class TestCreateSlaveOptions(OptionsMixin, unittest.TestCase):
    """
    Test buildslave.scripts.runner.CreateSlaveOptions class.
    """

    req_args = ["bdir", "mstr", "name", "pswd"]

    def parse(self, *args):
        opts = runner.CreateSlaveOptions()
        opts.parseOptions(args)
        return opts

    def test_defaults(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "incorrect number of arguments",
                                self.parse)

    def test_synopsis(self):
        opts = runner.CreateSlaveOptions()
        self.assertIn('buildslave create-slave', opts.getSynopsis())

    def test_min_args(self):

        # patch runner.MakerBase.postOptions() so that 'basedir'
        # argument will not be converted to absolute path
        self.patch(runner.MakerBase, "postOptions", mock.Mock())

        self.assertOptions(self.parse(*self.req_args),
                           dict(basedir="bdir", master="mstr",
                                name="name", passwd="pswd"))

    def test_all_args(self):

        # patch runner.MakerBase.postOptions() so that 'basedir'
        # argument will not be converted to absolute path
        self.patch(runner.MakerBase, "postOptions", mock.Mock())

        opts = self.parse("--force", "--relocatable", "--no-logrotate",
                          "--keepalive=4", "--usepty=0", "--umask=022",
                          "--maxdelay=3", "--log-size=2", "--log-count=1",
                          "--allow-shutdown=file", *self.req_args)
        self.assertOptions(opts,
                           {"force"          : True,
                            "relocatable"    : True,
                            "no-logrotate"   : True,
                            "usepty"         : 0,
                            "umask"          : "022",
                            "maxdelay"       : 3,
                            "log-size"       : 2,
                            "log-count"      : "1",
                            "allow-shutdown" : "file",
                            "basedir"        : "bdir",
                            "master"         : "mstr",
                            "name"           : "name",
                            "passwd"         : "pswd"})

    def test_master_url(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "<master> is not a URL - do not use URL",
                                self.parse, "a", "http://b.c", "d", "e")

    def test_inv_keepalive(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "keepalive parameter needs to be an number",
                                self.parse, "--keepalive=X", *self.req_args)

    def test_inv_usepty(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "usepty parameter needs to be an number",
                                self.parse, "--usepty=X", *self.req_args)

    def test_inv_maxdelay(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "maxdelay parameter needs to be an number",
                                self.parse, "--maxdelay=X", *self.req_args)

    def test_inv_log_size(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "log-size parameter needs to be an number",
                                self.parse, "--log-size=X", *self.req_args)

    def test_inv_log_count(self):
        self.assertRaisesRegexp(usage.UsageError,
                        "log-count parameter needs to be an number or None",
                        self.parse, "--log-count=X", *self.req_args)

    def test_too_few_args(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "incorrect number of arguments",
                                self.parse, "arg1", "arg2")

    def test_too_many_args(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "incorrect number of arguments",
                                self.parse, "extra_arg", *self.req_args)


class TestOptions(unittest.TestCase):
    """
    Test buildslave.scripts.runner.Options class.
    """
    def parse(self, *args):
        opts = runner.Options()
        opts.parseOptions(args)
        return opts

    def test_defaults(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "must specify a command",
                                self.parse)


# used by TestRun.test_run_good to patch in a callback
functionPlaceholder = None

class TestRun(misc.StdoutAssertionsMixin, unittest.TestCase):
    """
    Test buildslave.scripts.runner.run()
    """

    def setUp(self):
        self.setUpStdoutAssertions()

    class TestSubCommand(usage.Options):
        subcommandFunction = __name__ + ".functionPlaceholder"
        optFlags = [["test-opt", None, None]]

    class TestOptions(usage.Options):
        """
        Option class that emulates usage error. The 'suboptions' flag
        enables emulation of usage error in a sub-option.
        """
        optFlags = [["suboptions", None, None]]

        def postOptions(self):
            if self["suboptions"]:
                self.subOptions = "SubOptionUsage"
            raise usage.UsageError("usage-error-message")

        def __str__(self):
            return "GeneralUsage"

    def test_run_good(self):
        """
        Test successful invocation of buildslave command.
        """

        self.patch(sys, "argv", ["command", 'test', '--test-opt'])

        # patch runner module to use our test subcommand class
        self.patch(runner.Options, 'subCommands',
            [['test', None, self.TestSubCommand, None ]])

        # trace calls to subcommand function
        subcommand_func = mock.Mock(return_value = 42)
        self.patch(sys.modules[__name__],
                   "functionPlaceholder",
                   subcommand_func)

        # check that subcommand function called with correct arguments
        # and that it's return value is used as exit code
        exception = self.assertRaises(SystemExit, runner.run)
        subcommand_func.assert_called_once_with({'test-opt': 1})
        self.assertEqual(exception.code, 42, "unexpected exit code")

    def test_run_bad_noargs(self):
        """
        Test handling of invalid command line arguments.
        """
        self.patch(sys, "argv", ["command"])

        # patch runner module to use test Options class
        self.patch(runner, "Options", self.TestOptions)

        exception = self.assertRaises(SystemExit, runner.run)
        self.assertEqual(exception.code, 1, "unexpected exit code")
        self.assertStdoutEqual("command:  usage-error-message\n\n"
                               "GeneralUsage\n",
                               "unexpected error message on stdout")

    def test_run_bad_suboption(self):
        """
        Test handling of invalid command line arguments in a suboption.
        """

        self.patch(sys, "argv", ["command", "--suboptions"])

        # patch runner module to use test Options class
        self.patch(runner, "Options", self.TestOptions)

        exception = self.assertRaises(SystemExit, runner.run)
        self.assertEqual(exception.code, 1, "unexpected exit code")

        # check that we get error message for a sub-option
        self.assertStdoutEqual("command:  usage-error-message\n\n"
                               "SubOptionUsage\n",
                               "unexpected error message on stdout")

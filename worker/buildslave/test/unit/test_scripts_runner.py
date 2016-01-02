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

import mock
import os
import sys

from buildslave.scripts import runner
from buildslave.test.util import misc
from twisted.python import log
from twisted.python import usage
from twisted.trial import unittest


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


class BaseDirTestsMixin(object):

    """
    Common tests for Options classes with 'basedir' parameter
    """

    GETCWD_PATH = "test-dir"
    ABSPATH_PREFIX = "test-prefix-"
    MY_BASEDIR = "my-basedir"

    # the options class to instantiate for test cases
    options_class = None

    def setUp(self):
        self.patch(os, "getcwd", lambda: self.GETCWD_PATH)
        self.patch(os.path, "abspath", lambda path: self.ABSPATH_PREFIX + path)

    def parse(self, *args):
        assert self.options_class is not None

        opts = self.options_class()
        opts.parseOptions(args)
        return opts

    def test_defaults(self):
        opts = self.parse()
        self.assertEqual(opts["basedir"],
                         self.ABSPATH_PREFIX + self.GETCWD_PATH,
                         "unexpected basedir path")

    def test_basedir_arg(self):
        opts = self.parse(self.MY_BASEDIR)
        self.assertEqual(opts["basedir"],
                         self.ABSPATH_PREFIX + self.MY_BASEDIR,
                         "unexpected basedir path")

    def test_too_many_args(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "I wasn't expecting so many arguments",
                                self.parse, "arg1", "arg2")


class TestMakerBase(BaseDirTestsMixin, unittest.TestCase):

    """
    Test buildslave.scripts.runner.MakerBase class.
    """
    options_class = runner.MakerBase


class TestStopOptions(BaseDirTestsMixin, unittest.TestCase):

    """
    Test buildslave.scripts.runner.StopOptions class.
    """
    options_class = runner.StopOptions

    def test_synopsis(self):
        opts = runner.StopOptions()
        self.assertIn('buildslave stop', opts.getSynopsis())


class TestStartOptions(OptionsMixin, BaseDirTestsMixin, unittest.TestCase):

    """
    Test buildslave.scripts.runner.StartOptions class.
    """
    options_class = runner.StartOptions

    def test_synopsis(self):
        opts = runner.StartOptions()
        self.assertIn('buildslave start', opts.getSynopsis())

    def test_all_args(self):
        opts = self.parse("--quiet", "--nodaemon", self.MY_BASEDIR)
        self.assertOptions(opts,
                           dict(quiet=True, nodaemon=True,
                                basedir=self.ABSPATH_PREFIX + self.MY_BASEDIR))


class TestRestartOptions(OptionsMixin, BaseDirTestsMixin, unittest.TestCase):

    """
    Test buildslave.scripts.runner.RestartOptions class.
    """
    options_class = runner.RestartOptions

    def test_synopsis(self):
        opts = runner.RestartOptions()
        self.assertIn('buildslave restart', opts.getSynopsis())

    def test_all_args(self):
        opts = self.parse("--quiet", "--nodaemon", self.MY_BASEDIR)
        self.assertOptions(opts,
                           dict(quiet=True, nodaemon=True,
                                basedir=self.ABSPATH_PREFIX + self.MY_BASEDIR))


class TestUpgradeSlaveOptions(BaseDirTestsMixin, unittest.TestCase):

    """
    Test buildslave.scripts.runner.UpgradeSlaveOptions class.
    """
    options_class = runner.UpgradeSlaveOptions

    def test_synopsis(self):
        opts = runner.UpgradeSlaveOptions()
        self.assertIn('buildslave upgrade-slave', opts.getSynopsis())


class TestCreateSlaveOptions(OptionsMixin, unittest.TestCase):

    """
    Test buildslave.scripts.runner.CreateSlaveOptions class.
    """

    req_args = ["bdir", "mstr:5678", "name", "pswd"]

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
                           dict(basedir="bdir", host="mstr", port=5678,
                                name="name", passwd="pswd"))

    def test_all_args(self):

        # patch runner.MakerBase.postOptions() so that 'basedir'
        # argument will not be converted to absolute path
        self.patch(runner.MakerBase, "postOptions", mock.Mock())

        opts = self.parse("--force", "--relocatable", "--no-logrotate",
                          "--keepalive=4", "--usepty=0", "--umask=022",
                          "--maxdelay=3", "--numcpus=4", "--log-size=2", "--log-count=1",
                          "--allow-shutdown=file", *self.req_args)
        self.assertOptions(opts,
                           {"force": True,
                            "relocatable": True,
                            "no-logrotate": True,
                            "usepty": 0,
                            "umask": "022",
                            "maxdelay": 3,
                            "numcpus": "4",
                            "log-size": 2,
                            "log-count": "1",
                            "allow-shutdown": "file",
                            "basedir": "bdir",
                            "host": "mstr",
                            "port": 5678,
                            "name": "name",
                            "passwd": "pswd"})

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

    def test_inv_numcpus(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "numcpus parameter needs to be an number or None",
                                self.parse, "--numcpus=X", *self.req_args)

    def test_inv_umask(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "umask parameter needs to be an number or None",
                                self.parse, "--umask=X", *self.req_args)

    def test_inv_allow_shutdown(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "allow-shutdown needs to be one of 'signal' or 'file'",
                                self.parse, "--allow-shutdown=X", *self.req_args)

    def test_too_few_args(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "incorrect number of arguments",
                                self.parse, "arg1", "arg2")

    def test_too_many_args(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "incorrect number of arguments",
                                self.parse, "extra_arg", *self.req_args)

    def test_validateMasterArgument_no_port(self):
        """
        test calling CreateSlaveOptions.validateMasterArgument()
        on <master> argument without port specified.
        """
        opts = runner.CreateSlaveOptions()
        self.assertEqual(opts.validateMasterArgument("mstrhost"),
                         ("mstrhost", 9989),
                         "incorrect master host and/or port")

    def test_validateMasterArgument_empty_master(self):
        """
        test calling CreateSlaveOptions.validateMasterArgument()
        on <master> without host part specified.
        """
        opts = runner.CreateSlaveOptions()
        self.assertRaisesRegexp(usage.UsageError,
                                "invalid <master> argument ':1234'",
                                opts.validateMasterArgument, ":1234")

    def test_validateMasterArgument_inv_port(self):
        """
        test calling CreateSlaveOptions.validateMasterArgument()
        on <master> without with unparsable port part
        """
        opts = runner.CreateSlaveOptions()
        self.assertRaisesRegexp(usage.UsageError,
                                "invalid master port 'apple', "
                                "needs to be an number",
                                opts.validateMasterArgument, "host:apple")

    def test_validateMasterArgument_ok(self):
        """
        test calling CreateSlaveOptions.validateMasterArgument()
        on <master> without host and port parts specified.
        """
        opts = runner.CreateSlaveOptions()
        self.assertEqual(opts.validateMasterArgument("mstrhost:4321"),
                         ("mstrhost", 4321),
                         "incorrect master host and/or port")


class TestOptions(misc.LoggingMixin, unittest.TestCase):

    """
    Test buildslave.scripts.runner.Options class.
    """

    def setUp(self):
        self.setUpLogging()

    def parse(self, *args):
        opts = runner.Options()
        opts.parseOptions(args)
        return opts

    def test_defaults(self):
        self.assertRaisesRegexp(usage.UsageError,
                                "must specify a command",
                                self.parse)

    def test_version(self):
        exception = self.assertRaises(SystemExit, self.parse, '--version')
        self.assertEqual(exception.code, 0, "unexpected exit code")
        self.assertLogged('Buildslave version:')

    def test_verbose(self):
        self.patch(log, 'startLogging', mock.Mock())
        self.assertRaises(usage.UsageError, self.parse, "--verbose")
        log.startLogging.assert_called_once_with(sys.stderr)


# used by TestRun.test_run_good to patch in a callback
functionPlaceholder = None


class TestRun(misc.LoggingMixin, unittest.TestCase):

    """
    Test buildslave.scripts.runner.run()
    """

    def setUp(self):
        self.setUpLogging()

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
                   [['test', None, self.TestSubCommand, None]])

        # trace calls to subcommand function
        subcommand_func = mock.Mock(return_value=42)
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
        self.assertLogged("command:  usage-error-message",
                          "GeneralUsage",
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
        self.assertLogged("command:  usage-error-message",
                          "SubOptionUsage",
                          "unexpected error message on stdout")

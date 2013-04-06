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
from twisted.trial import unittest
from twisted.python import usage
from buildslave.scripts import runner, base

class TestUpgradeSlave(unittest.TestCase):
    """
    Test buildslave.scripts.runner.upgradeSlave()
    """

    def test_upgradeSlave_bad_basedir(self):
        """
        test calling upgradeSlave() with bad base directory
        """
        # override isBuildslaveDir() to always fail
        mocked_isBuildslaveDir = mock.Mock(return_value=False)
        self.patch(base, "isBuildslaveDir", mocked_isBuildslaveDir)

        # call upgradeSlave() and check that SystemExit exception is raised
        config = {"basedir" : "dummy"}
        exception = self.assertRaises(SystemExit, runner.upgradeSlave, config)

        # check exit code
        self.assertEqual(exception.code, 1, "unexpected exit code")

        # check that isBuildslaveDir was called with correct argument
        mocked_isBuildslaveDir.assert_called_once_with("dummy")


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

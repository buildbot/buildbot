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

from __future__ import absolute_import
from __future__ import print_function
from future.builtins import range
from future.moves.urllib import request as urllib_request

import os
import platform
from unittest.case import SkipTest

from twisted.internet import reactor
from twisted.python.filepath import FilePath
from twisted.trial import unittest

import buildbot.buildbot_net_usage_data
from buildbot import config
from buildbot.buildbot_net_usage_data import _sendBuildbotNetUsageData
from buildbot.buildbot_net_usage_data import computeUsageData
from buildbot.buildbot_net_usage_data import linux_distribution
from buildbot.config import BuilderConfig
from buildbot.config import ConfigWarning
from buildbot.master import BuildMaster
from buildbot.plugins import steps
from buildbot.process.factory import BuildFactory
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.test.util.integration import DictLoader
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker.base import Worker


class Tests(unittest.TestCase):

    def getMaster(self, config_dict):
        """
        Create a started ``BuildMaster`` with the given configuration.
        """
        basedir = FilePath(self.mktemp())
        basedir.createDirectory()
        master = BuildMaster(
            basedir.path, reactor=reactor, config_loader=DictLoader(config_dict))
        master.config = master.config_loader.loadConfig()
        return master

    def getBaseConfig(self):
        return {
            'builders': [
                BuilderConfig(name="testy",
                              workernames=["local1", "local2"],
                              factory=BuildFactory([steps.ShellCommand(command='echo hello')])),
            ],
            'workers': [Worker('local' + str(i), 'pass') for i in range(3)],
            'schedulers': [
                ForceScheduler(
                    name="force",
                    builderNames=["testy"])
            ],
            'protocols': {'null': {}},
            'multiMaster': True,
        }

    def test_basic(self):
        self.patch(config, "_in_unit_tests", False)
        with assertProducesWarning(
                ConfigWarning,
                message_pattern=r"`buildbotNetUsageData` is not configured and defaults to basic."):
            master = self.getMaster(self.getBaseConfig())
        data = computeUsageData(master)
        self.assertEqual(sorted(data.keys()),
                         sorted(['versions', 'db', 'platform', 'installid', 'mq', 'plugins', 'www_plugins']))
        self.assertEqual(data['plugins']['buildbot/worker/base/Worker'], 3)
        self.assertEqual(sorted(data['plugins'].keys()), sorted(
            ['buildbot/schedulers/forcesched/ForceScheduler', 'buildbot/worker/base/Worker',
             'buildbot/steps/shell/ShellCommand', 'buildbot/config/BuilderConfig']))

    def test_full(self):
        c = self.getBaseConfig()
        c['buildbotNetUsageData'] = 'full'
        master = self.getMaster(c)
        data = computeUsageData(master)
        self.assertEqual(sorted(data.keys()),
                         sorted(['versions', 'db', 'installid', 'platform', 'mq', 'plugins',
                                 'builders', 'www_plugins']))

    def test_custom(self):
        c = self.getBaseConfig()

        def myCompute(data):
            return dict(db=data['db'])
        c['buildbotNetUsageData'] = myCompute
        master = self.getMaster(c)
        data = computeUsageData(master)
        self.assertEqual(sorted(data.keys()),
                         sorted(['db']))

    def test_urllib(self):
        self.patch(buildbot.buildbot_net_usage_data, '_sendWithRequests', lambda _, __: None)

        class FakeRequest(object):

            def __init__(self, *args, **kwargs):
                self.args = args
                self.kwargs = kwargs

        open_url = []

        class urlopen(object):

            def __init__(self, r):
                self.request = r
                open_url.append(self)

            def read(self):
                return "ok"

            def close(self):
                pass

        self.patch(urllib_request, "Request", FakeRequest)
        self.patch(urllib_request, "urlopen", urlopen)
        _sendBuildbotNetUsageData({'foo': 'bar'})
        self.assertEqual(len(open_url), 1)
        self.assertEqual(open_url[0].request.args,
                         ('https://events.buildbot.net/events/phone_home',
                          b'{"foo": "bar"}',
                          {'Content-Length': 14, 'Content-Type': 'application/json'}))

    def test_real(self):
        if "TEST_BUILDBOTNET_USAGEDATA" not in os.environ:
            raise SkipTest(
                "_sendBuildbotNetUsageData real test only run when environment variable"
                " TEST_BUILDBOTNET_USAGEDATA is set")

        _sendBuildbotNetUsageData({'foo': 'bar'})

    def test_linux_distro(self):
        system = platform.system()
        if system != "Linux":
            raise SkipTest("test is only for linux")
        distro = linux_distribution()
        self.assertEqual(len(distro), 2)
        self.assertNotIn("unknown", distro[0])
        self.assertNotIn("unknown", distro[1])

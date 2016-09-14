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

import urllib2

from twisted.internet import reactor
from twisted.python.filepath import FilePath
from twisted.trial import unittest

from buildbot.buildbot_net_usage_data import _sendBuildbotNetUsageData
from buildbot.buildbot_net_usage_data import computeUsageData
from buildbot.config import BuilderConfig
from buildbot.master import BuildMaster
from buildbot.plugins import steps
from buildbot.process.factory import BuildFactory
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.test.util.integration import DictLoader
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
            'workers': [Worker('local' + str(i), 'pass') for i in xrange(3)],
            'schedulers': [
                ForceScheduler(
                    name="force",
                    builderNames=["testy"])
            ],
            'protocols': {'null': {}},
            'multiMaster': True,
        }

    def test_basic(self):
        master = self.getMaster(self.getBaseConfig())
        data = computeUsageData(master)
        self.assertEquals(sorted(data.keys()),
                          sorted(['versions', 'db', 'platform', 'installid', 'mq', 'plugins', 'www_plugins']))
        self.assertEquals(data['plugins']['buildbot/worker/base/Worker'], 3)
        self.assertEquals(sorted(data['plugins'].keys()), sorted(
            ['buildbot/schedulers/forcesched/ForceScheduler', 'buildbot/worker/base/Worker',
             'buildbot/steps/shell/ShellCommand', 'buildbot/config/BuilderConfig']))

    def test_full(self):
        c = self.getBaseConfig()
        c['buildbotNetUsageData'] = 'full'
        master = self.getMaster(c)
        data = computeUsageData(master)
        self.assertEquals(sorted(data.keys()),
                          sorted(['versions', 'db', 'installid', 'platform', 'mq', 'plugins',
                                  'builders', 'www_plugins']))

    def test_custom(self):
        c = self.getBaseConfig()

        def myCompute(data):
            return dict(db=data['db'])
        c['buildbotNetUsageData'] = myCompute
        master = self.getMaster(c)
        data = computeUsageData(master)
        self.assertEquals(sorted(data.keys()),
                          sorted(['db']))

    def test_urllib2(self):

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

        self.patch(urllib2, "Request", FakeRequest)
        self.patch(urllib2, "urlopen", urlopen)
        _sendBuildbotNetUsageData({'foo': 'bar'})
        self.assertEqual(len(open_url), 1)
        self.assertEqual(open_url[0].request.args,
                        ('https://events.buildbot.net/events/phone_home',
                         '{"foo": "bar"}', {'Content-Length': 14, 'Content-Type': 'application/json'}))

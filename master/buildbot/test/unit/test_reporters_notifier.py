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


from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters.message import MessageFormatter
from buildbot.reporters.notifier import NotifierBase
from buildbot.test.fake import fakemaster
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.notifier import NotifierTestMixin


class TestMailNotifier(ConfigErrorsMixin, TestReactorMixin,
                       unittest.TestCase, NotifierTestMixin):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    @defer.inlineCallbacks
    def setupNotifier(self, *args, **kwargs):
        mn = NotifierBase(*args, **kwargs)
        mn.sendMessage = Mock(spec=mn.sendMessage)
        mn.sendMessage.return_value = "<message>"
        yield mn.setServiceParent(self.master)
        yield mn.startService()
        return mn

    @defer.inlineCallbacks
    def setupBuildMessage(self, **mnKwargs):

        _, builds = yield self.setupBuildResults(FAILURE)

        formatter = Mock(spec=MessageFormatter)
        formatter.formatMessageForBuildResults.return_value = {"body": "body",
                                                               "type": "text",
                                                               "subject": "subject"}
        formatter.wantProperties = False
        formatter.wantSteps = False
        formatter.wantLogs = False

        mn = yield self.setupNotifier(messageFormatter=formatter, **mnKwargs)

        yield mn._got_event(('builds', 97, 'finished'), builds[0])
        return (mn, builds, formatter)

    @defer.inlineCallbacks
    def test_buildMessage_nominal(self):
        mn, builds, formatter = yield self.setupBuildMessage(mode=("change",))

        build = builds[0]
        formatter.formatMessageForBuildResults.assert_called_with(
            ('change',), 'Builder1', build['buildset'], build, self.master, SUCCESS, ['me@foo'])

        report = {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'builder_name': 'Builder1',
            'results': FAILURE,
            'builds': builds,
            'users': ['me@foo'],
            'patches': [],
            'logs': []
        }

        self.assertEqual(mn.sendMessage.call_count, 1)
        mn.sendMessage.assert_called_with([report])

    @defer.inlineCallbacks
    def test_worker_missing_sends_message(self):

        mn = yield self.setupNotifier(watchedWorkers=['myworker'])

        worker_dict = {
            'name': 'myworker',
            'notify': ["workeradmin@example.org"],
            'workerinfo': {"admin": "myadmin"},
            'last_connection': "yesterday"
        }
        yield mn._got_event(('workers', 98, 'missing'), worker_dict)

        self.assertEqual(mn.sendMessage.call_count, 1)

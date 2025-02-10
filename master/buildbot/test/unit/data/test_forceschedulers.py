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


from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import forceschedulers
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.test import fakedb
from buildbot.test.util import endpoint

expected_default = {
    'all_fields': [
        {
            'columns': 1,
            'autopopulate': None,
            'default': '',
            'fields': [
                {
                    'default': '',
                    'autopopulate': None,
                    'fullName': 'username',
                    'hide': False,
                    'label': 'Your name:',
                    'maxsize': None,
                    'multiple': False,
                    'name': 'username',
                    'need_email': True,
                    'regex': None,
                    'required': False,
                    'size': 30,
                    'tablabel': 'Your name:',
                    'type': 'username',
                    'tooltip': '',
                },
                {
                    'default': 'force build',
                    'autopopulate': None,
                    'fullName': 'reason',
                    'hide': False,
                    'label': 'reason',
                    'maxsize': None,
                    'multiple': False,
                    'name': 'reason',
                    'regex': None,
                    'required': False,
                    'size': 20,
                    'tablabel': 'reason',
                    'type': 'text',
                    'tooltip': '',
                },
                {
                    'default': 0,
                    'autopopulate': None,
                    'fullName': 'priority',
                    'hide': False,
                    'label': 'priority',
                    'maxsize': None,
                    'multiple': False,
                    'name': 'priority',
                    'regex': None,
                    'required': False,
                    'size': 10,
                    'tablabel': 'priority',
                    'type': 'int',
                    'tooltip': '',
                },
            ],
            'fullName': None,
            'hide': False,
            'label': '',
            'layout': 'vertical',
            'maxsize': None,
            'multiple': False,
            'name': '',
            'regex': None,
            'required': False,
            'tablabel': '',
            'type': 'nested',
            'tooltip': '',
        },
        {
            'columns': 2,
            'default': '',
            'fields': [
                {
                    'default': '',
                    'autopopulate': None,
                    'fullName': 'branch',
                    'hide': False,
                    'label': 'Branch:',
                    'multiple': False,
                    'maxsize': None,
                    'name': 'branch',
                    'regex': None,
                    'required': False,
                    'size': 10,
                    'tablabel': 'Branch:',
                    'type': 'text',
                    'tooltip': '',
                },
                {
                    'default': '',
                    'autopopulate': None,
                    'fullName': 'project',
                    'hide': False,
                    'label': 'Project:',
                    'maxsize': None,
                    'multiple': False,
                    'name': 'project',
                    'regex': None,
                    'required': False,
                    'size': 10,
                    'tablabel': 'Project:',
                    'type': 'text',
                    'tooltip': '',
                },
                {
                    'default': '',
                    'autopopulate': None,
                    'fullName': 'repository',
                    'hide': False,
                    'label': 'Repository:',
                    'maxsize': None,
                    'multiple': False,
                    'name': 'repository',
                    'regex': None,
                    'required': False,
                    'size': 10,
                    'tablabel': 'Repository:',
                    'type': 'text',
                    'tooltip': '',
                },
                {
                    'default': '',
                    'autopopulate': None,
                    'fullName': 'revision',
                    'hide': False,
                    'label': 'Revision:',
                    'maxsize': None,
                    'multiple': False,
                    'name': 'revision',
                    'regex': None,
                    'required': False,
                    'size': 10,
                    'tablabel': 'Revision:',
                    'type': 'text',
                    'tooltip': '',
                },
            ],
            'autopopulate': None,
            'fullName': None,
            'hide': False,
            'label': '',
            'layout': 'vertical',
            'maxsize': None,
            'multiple': False,
            'name': '',
            'regex': None,
            'required': False,
            'tablabel': '',
            'type': 'nested',
            'tooltip': '',
        },
    ],
    'builder_names': ['builder'],
    'button_name': 'defaultforce',
    'label': 'defaultforce',
    'name': 'defaultforce',
    'enabled': True,
}


class ForceschedulerEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = forceschedulers.ForceSchedulerEndpoint
    resourceTypeClass = forceschedulers.ForceScheduler
    maxDiff = None

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpEndpoint()
        scheds = [ForceScheduler(name="defaultforce", builderNames=["builder"])]
        self.master.allSchedulers = lambda: scheds
        for sched in scheds:
            yield sched.setServiceParent(self.master)
        yield self.master.db.insert_test_data([
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
        ])
        yield self.master.startService()

    @defer.inlineCallbacks
    def test_get_existing(self):
        res = yield self.callGet(('forceschedulers', "defaultforce"))
        self.validateData(res)
        self.assertEqual(res, expected_default)

    @defer.inlineCallbacks
    def test_get_missing(self):
        res = yield self.callGet(('forceschedulers', 'foo'))
        self.assertEqual(res, None)


class ForceSchedulersEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = forceschedulers.ForceSchedulersEndpoint
    resourceTypeClass = forceschedulers.ForceScheduler
    maxDiff = None

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpEndpoint()
        scheds = [ForceScheduler(name="defaultforce", builderNames=["builder"])]
        self.master.allSchedulers = lambda: scheds
        for sched in scheds:
            yield sched.setServiceParent(self.master)
        yield self.master.db.insert_test_data([
            fakedb.Master(id=fakedb.FakeDBConnector.MASTER_ID),
        ])
        yield self.master.startService()

    @defer.inlineCallbacks
    def test_get_existing(self):
        res = yield self.callGet(('forceschedulers',))
        self.assertEqual(res, [expected_default])

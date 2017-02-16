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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import forceschedulers
from buildbot.schedulers.forcesched import ForceScheduler
from buildbot.test.util import endpoint

expected_default = {
    'all_fields': [{'columns': 1,
                    'default': '',
                    'fields': [{'default': 'force build',
                                'fullName': 'reason',
                                'hide': False,
                                'label': 'reason',
                                'multiple': False,
                                'name': 'reason',
                                'regex': None,
                                'required': False,
                                'size': 20,
                                'tablabel': 'reason',
                                'type': 'text'},
                               {'default': '',
                                'fullName': 'username',
                                'hide': False,
                                'label': 'Your name:',
                                'multiple': False,
                                'name': 'username',
                                'need_email': True,
                                'regex': None,
                                'required': False,
                                'size': 30,
                                'tablabel': 'Your name:',
                                'type': 'username'}],
                    'fullName': None,
                    'hide': False,
                    'label': '',
                    'layout': 'vertical',
                    'multiple': False,
                    'name': '',
                    'regex': None,
                    'required': False,
                    'tablabel': '',
                    'type': 'nested'},
                   {'columns': 2,
                    'default': '',
                    'fields': [{'default': '',
                                'fullName': 'branch',
                                'hide': False,
                                'label': 'Branch:',
                                'multiple': False,
                                'name': 'branch',
                                'regex': None,
                                'required': False,
                                'size': 10,
                                'tablabel': 'Branch:',
                                'type': 'text'},
                               {'default': '',
                                'fullName': 'project',
                                'hide': False,
                                'label': 'Project:',
                                'multiple': False,
                                'name': 'project',
                                'regex': None,
                                'required': False,
                                'size': 10,
                                'tablabel': 'Project:',
                                'type': 'text'},
                               {'default': '',
                                'fullName': 'repository',
                                'hide': False,
                                'label': 'Repository:',
                                'multiple': False,
                                'name': 'repository',
                                'regex': None,
                                'required': False,
                                'size': 10,
                                'tablabel': 'Repository:',
                                'type': 'text'},
                               {'default': '',
                                'fullName': 'revision',
                                'hide': False,
                                'label': 'Revision:',
                                'multiple': False,
                                'name': 'revision',
                                'regex': None,
                                'required': False,
                                'size': 10,
                                'tablabel': 'Revision:',
                                'type': 'text'}],
                    'fullName': None,
                    'hide': False,
                    'label': '',
                    'layout': 'vertical',
                    'multiple': False,
                    'name': '',
                    'regex': None,
                    'required': False,
                    'tablabel': '',
                    'type': 'nested'}],
    'builder_names': [u'builder'],
    'button_name': u'defaultforce',
    'label': u'defaultforce',
    'name': u'defaultforce',
    'enabled': True}


class ForceschedulerEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = forceschedulers.ForceSchedulerEndpoint
    resourceTypeClass = forceschedulers.ForceScheduler

    def setUp(self):
        self.setUpEndpoint()
        scheds = [ForceScheduler(
            name="defaultforce",
            builderNames=["builder"])]
        self.master.allSchedulers = lambda: scheds

    def tearDown(self):
        self.tearDownEndpoint()

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

    def setUp(self):
        self.setUpEndpoint()
        scheds = [ForceScheduler(
            name="defaultforce",
            builderNames=["builder"])]
        self.master.allSchedulers = lambda: scheds

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get_existing(self):
        res = yield self.callGet(('forceschedulers', ))
        self.assertEqual(res, [expected_default])

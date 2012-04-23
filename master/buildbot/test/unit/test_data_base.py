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

from twisted.trial import unittest
from buildbot.data import base
from buildbot.test.util import endpoint

class MyEndpoint(base.Endpoint):

    pathPattern = ('foo', ':foo', 'bar')


class Endpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = MyEndpoint

    def setUp(self):
        self.setUpEndpoint(needDB=False)

    def tearDown(self):
        self.tearDownEndpoint()

    def patchMatcher(self):
        self.ep.matcher

    def test_sets_master(self):
        self.assertIdentical(self.master, self.ep.master)

    def test_getSubscriptionTopic(self):
        self.patch(MyEndpoint, 'pathTopicTemplate', 'foo.%(foo)s.#.bar')
        self.assertEqual(self.ep.getSubscriptionTopic({}, dict(foo='f')),
                'foo.f.#.bar')

    def test_getSubscriptionTopic_SafeDict(self):
        self.patch(MyEndpoint, 'pathTopicTemplate', 'foo.%(foo)s.#.bar')
        self.assertEqual(self.ep.getSubscriptionTopic({}, dict(foo='f.g')),
                'foo.f_g.#.bar')

    def test_getSubscriptionTopic_no_subs(self):
        self.patch(MyEndpoint, 'pathTopicTemplate', 'foo.*.bar')
        self.assertEqual(self.ep.getSubscriptionTopic({}, dict(foo='f')),
                'foo.*.bar')

    def test_getSubscriptionTopic_no_topic(self):
        self.assertEqual(self.ep.getSubscriptionTopic({}, dict(foo='f')),
                None)


class SafeDict(unittest.TestCase):

    def setUp(self):
        self.d = base.SafeDict(dict(good='abcd', bad_dot='a.c',
                        bad_star='a*c', bad_hash='a#c'))

    def test_good(self):
        self.assertEqual(self.d['good'], 'abcd')

    def test_bad_dot(self):
        self.assertEqual(self.d['bad_dot'], 'a_c')

    def test_bad_star(self):
        self.assertEqual(self.d['bad_star'], 'a_c')

    def test_bad_hash(self):
        self.assertEqual(self.d['bad_hash'], 'a_c')

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

from buildbot.status.web import base
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake.web import FakeRequest


class ActionResource(unittest.TestCase):

    def test_ActionResource_success(self):

        class MyActionResource(base.ActionResource):

            def performAction(self, request):
                self.got_request = request
                return defer.succeed('http://buildbot.net')

        rsrc = MyActionResource()
        request = FakeRequest()
        rsrc.render(request)
        d = request.deferred

        def check(_):
            self.assertIdentical(rsrc.got_request, request)
            self.assertTrue(request.finished)
            self.assertIn('buildbot.net', request.written)
            self.assertEqual(request.redirected_to, 'http://buildbot.net')
        d.addCallback(check)
        return d

    def test_ActionResource_exception(self):

        class MyActionResource(base.ActionResource):

            def performAction(self, request):
                return defer.fail(RuntimeError('sacrebleu'))

        rsrc = MyActionResource()
        request = FakeRequest()
        rsrc.render(request)
        d = request.deferred

        def check(f):
            f.trap(RuntimeError)
            # pass - all good!
        d.addErrback(check)
        return d


class Functions(unittest.TestCase):

    def do_test_getRequestCharset(self, hdr, exp):
        req = mock.Mock()
        req.getHeader.return_value = hdr

        self.assertEqual(base.getRequestCharset(req), exp)

    def fakeRequest(self, prepath):
        r = mock.Mock()
        r.prepath = prepath
        return r

    def test_getRequestCharset_empty(self):
        return self.do_test_getRequestCharset(None, 'utf-8')

    def test_getRequestCharset_specified(self):
        return self.do_test_getRequestCharset(
            'application/x-www-form-urlencoded ; charset=ISO-8859-1',
            'ISO-8859-1')

    def test_getRequestCharset_other_params(self):
        return self.do_test_getRequestCharset(
            'application/x-www-form-urlencoded ; charset=UTF-16 ; foo=bar',
            'UTF-16')

    def test_plural_zero(self):
        self.assertEqual(base.plural("car", "cars", 0), "0 cars")

    def test_plural_one(self):
        self.assertEqual(base.plural("car", "cars", 1), "1 car")

    def test_plural_many(self):
        self.assertEqual(base.plural("car", "cars", 34), "34 cars")

    def test_abbreviate_age_0_sec(self):
        self.assertEqual(base.abbreviate_age(0), "0 seconds ago")

    def test_abbreviate_age_1_sec(self):
        self.assertEqual(base.abbreviate_age(1), "1 second ago")

    def test_abbreviate_age_5_sec(self):
        self.assertEqual(base.abbreviate_age(5), "5 seconds ago")

    def test_abbreviate_age_89_sec(self):
        self.assertEqual(base.abbreviate_age(89), "89 seconds ago")

    def test_abbreviate_age_2_min(self):
        self.assertEqual(base.abbreviate_age((base.MINUTE * 2) + 2),
                         "about 2 minutes ago")

    def test_abbreviate_age_10_min(self):
        self.assertEqual(base.abbreviate_age((base.MINUTE * 10) + 7),
                         "about 10 minutes ago")

    def test_abbreviate_age_64_min(self):
        self.assertEqual(base.abbreviate_age((base.HOUR + base.MINUTE * 4)),
                         "about 64 minutes ago")

    def test_abbreviate_age_2_hours(self):
        self.assertEqual(base.abbreviate_age((base.HOUR * 2 + 25)),
                         "about 2 hours ago")

    def test_abbreviate_age_1_day(self):
        self.assertEqual(base.abbreviate_age((base.DAY + base.MINUTE * 4)),
                         "about 1 day ago")

    def test_abbreviate_age_3_days(self):
        self.assertEqual(base.abbreviate_age((base.DAY * 3 + base.MINUTE * 9)),
                         "about 3 days ago")

    def test_abbreviate_age_12_days(self):
        self.assertEqual(base.abbreviate_age((base.DAY * 12 + base.HOUR * 9)),
                         "about 12 days ago")

    def test_abbreviate_age_3_weeks(self):
        self.assertEqual(base.abbreviate_age((base.WEEK * 3 + base.DAY)),
                         "about 3 weeks ago")

    def test_abbreviate_age_long_time(self):
        self.assertEqual(base.abbreviate_age((base.MONTH * 4 + base.WEEK)),
                         "a long time ago")

    def test_path_to_root_from_root(self):
        self.assertEqual(base.path_to_root(self.fakeRequest([])),
                         './')

    def test_path_to_root_from_one_level(self):
        self.assertEqual(base.path_to_root(self.fakeRequest(['waterfall'])),
                         './')

    def test_path_to_root_from_two_level(self):
        self.assertEqual(base.path_to_root(self.fakeRequest(['a', 'b'])),
                         '../')

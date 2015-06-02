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
# Copyright 2013 (c) - Manba Team

import os
import random


from twisted.trial import unittest
from twisted.internet.defer import inlineCallbacks

from buildbot.status import results
from buildbot.status.web import pngstatus
from buildbot.test.fake.web import FakeRequest


class TestPngStatusResource(unittest.TestCase):
    """Simple unit tests to check Png Status resource
    """

    def setUp(self):
        self.request_data = {
            'builder': ['TestBuilder'],
            'size': 'normal',
        }

        self.request = FakeRequest(self.request_data)
        self.request.uri = '/png'
        self.request.method = 'GET'

    @inlineCallbacks
    def testReturnedUnknownPngOnunkwnownBuilder(self):
        status = FakeStatus()
        self.request = FakeRequest({'builder': ':)', 'size': 'normal'})
        self.request.uri = '/png'
        self.request.method = 'GET'
        yield self.request.test_render(pngstatus.PngStatusResource(status))

        png_file = open(
            '%s/../../status/web/files/unknown_normal.png' % (
                os.path.dirname(__file__),), 'rb'
        )
        png = png_file.read()
        png_file.close()
        self.assertEqual(self.request.written, png)

    @inlineCallbacks
    def testReturnedSuccesPngOnSuccesBuild(self):
        status = FakeStatus()
        yield self.request.test_render(pngstatus.PngStatusResource(status))

        png_file = open(
            '%s/../../status/web/files/success_normal.png' % (
                os.path.dirname(__file__),), 'rb'
        )
        png = png_file.read()
        png_file.close()
        self.assertEqual(self.request.written, png)

    @inlineCallbacks
    def testReturnedSuccesPngOnWheteverStatusBuild(self):
        i = random.randint(0, 5)
        status = FakeStatus()
        FakeBuilder.status_code = i
        yield self.request.test_render(pngstatus.PngStatusResource(status))

        png_file = open(
            '%s/../../status/web/files/%s_normal.png' % (
                os.path.dirname(__file__), results.Results[i]), 'rb'
        )
        png = png_file.read()
        png_file.close()
        self.assertEqual(self.request.written, png)

    @inlineCallbacks
    def testReturnedWheteverStatusAndWhateverSize(self):
        sizes = [['small'], ['normal'], ['large']]
        i = random.randint(0, 5)
        x = sizes[random.randint(0, 2)]
        status = FakeStatus()
        FakeBuilder.status_code = i

        request_data = self.request_data.copy()
        request_data['size'] = x
        self.request = FakeRequest(request_data)
        self.request.uri = '/png'
        self.request.method = 'GET'

        yield self.request.test_render(pngstatus.PngStatusResource(status))

        png_file = open(
            '%s/../../status/web/files/%s_%s.png' % (
                os.path.dirname(__file__), results.Results[i], x[0]), 'rb'
        )
        png = png_file.read()
        png_file.close()
        self.assertEqual(self.request.written, png)


class FakeStatus(object):
    """Just a Fake Status object
    """

    def getBuilderNames(self):
        return ['TestBuilder']

    def getBuilder(self, ignore):

        return FakeBuilder()


class FakeBuilder(object):
    """Just a Fake Builder :)
    """

    def getBuild(self, number=0):
        self.number = number
        return self

    def getResults(self):
        if hasattr(self, 'status_code'):
            return self.status_code

        return 0

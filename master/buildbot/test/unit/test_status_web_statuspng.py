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

from twisted.internet.defer import inlineCallbacks
from twisted.trial import unittest

from buildbot.status import results
from buildbot.status.web import pngstatus
from buildbot.test.fake.web import FakeRequest

sizes = ['small', 'normal', 'large']
png_files = dict(
    ('%s_%s' % (status, size),
        open('%s/../../status/web/files/%s_%s.png' %
            (os.path.dirname(__file__), status, size), 'rb').read())
    for size in sizes
    for status in results.Results + ['unknown']
)
png_files_by_contents = dict((y, x) for (x, y) in png_files.iteritems())


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

    def assertPngFile(self, png, expectedFilename):
        gotFilename = png_files_by_contents.get(png, png)
        self.assertEqual(gotFilename, expectedFilename)

    @inlineCallbacks
    def testReturnedUnknownPngOnUnkwnownBuilder(self):
        status = FakeStatus()
        self.request = FakeRequest({'builder': [':)'], 'size': 'normal'})
        self.request.uri = '/png'
        self.request.method = 'GET'
        yield self.request.test_render(pngstatus.PngStatusResource(status))

        self.assertPngFile(self.request.written, 'unknown_normal')

    @inlineCallbacks
    def testReturnedSuccesPngOnSuccesBuild(self):
        status = FakeStatus()
        yield self.request.test_render(pngstatus.PngStatusResource(status))

        self.assertPngFile(self.request.written, 'success_normal')

    @inlineCallbacks
    def do_test(self, size, status_code, exp):
        status = FakeStatus(status_code)
        if size:
            self.request_data['size'] = [size]
        yield self.request.test_render(pngstatus.PngStatusResource(status))

        self.assertPngFile(self.request.written, exp)

# add methods to the class for each combination
for size in None, 'small', 'normal', 'large':
    for status_code in range(len(results.Results)):
        status = results.Results[status_code]
        func_name = 'test_%s_%s' % (status, size or 'unspec')
        exp = '%s_%s' % (status, size or 'normal')
        setattr(TestPngStatusResource, func_name,
                lambda self, size=size, status_code=status_code, exp=exp:
                self.do_test(size, status_code, exp))


class FakeStatus(object):

    def __init__(self, status_code=results.SUCCESS):
        self._status_code = status_code

    def getBuilderNames(self):
        return ['TestBuilder']

    def getBuilder(self, ignore):
        return FakeBuilder(self._status_code)


class FakeBuilder(object):

    def __init__(self, status_code):
        self._status_code = status_code

    def getBuild(self, number=0, revision=None):
        return FakeBuild(self._status_code)


class FakeBuild(object):

    def __init__(self, status_code):
        self._status_code = status_code

    def getResults(self):
        return self._status_code

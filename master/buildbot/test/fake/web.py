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

from io import BytesIO

from mock import Mock

from twisted.internet import defer
from twisted.web import server

from buildbot.test.fake import fakemaster


def fakeMasterForHooks(testcase):
    # testcase must derive from TestReactorMixin and setUpTestReactor()
    # must be called before calling this function.

    master = fakemaster.make_master(testcase, wantData=True)
    master.www = Mock()
    return master


class FakeRequest(Mock):

    """
    A fake Twisted Web Request object, including some pointers to the
    buildmaster and an addChange method on that master which will append its
    arguments to self.addedChanges.
    """

    written = b''
    finished = False
    redirected_to = None
    failure = None

    def __init__(self, args=None, content=b''):
        super().__init__()

        if args is None:
            args = {}

        self.args = args
        self.content = BytesIO(content)
        self.site = Mock()
        self.site.buildbot_service = Mock()
        self.uri = b'/'
        self.prepath = []
        self.method = b'GET'
        self.received_headers = {}

        self.deferred = defer.Deferred()

    def getHeader(self, key):
        return self.received_headers.get(key)

    def write(self, data):
        self.written = self.written + data

    def redirect(self, url):
        self.redirected_to = url

    def finish(self):
        self.finished = True
        self.deferred.callback(None)

    def processingFailed(self, f):
        self.deferred.errback(f)

    # work around http://code.google.com/p/mock/issues/detail?id=105
    def _get_child_mock(self, **kw):
        return Mock(**kw)

    # cribed from twisted.web.test._util._render
    def test_render(self, resource):
        for arg in self.args:
            if not isinstance(arg, bytes):
                raise ValueError("self.args: {!r},  contains "
                    "values which are not bytes".format(self.args))

        if self.uri and not isinstance(self.uri, bytes):
            raise ValueError("self.uri: {!r} is {}, not bytes".format(
                self.uri, type(self.uri)))

        if self.method and not isinstance(self.method, bytes):
            raise ValueError("self.method: {!r} is {}, not bytes".format(
                self.method, type(self.method)))

        result = resource.render(self)
        if isinstance(result, bytes):
            self.write(result)
            self.finish()
            return self.deferred
        elif isinstance(result, str):
            raise ValueError("{!r} should return bytes, not {}: {!r}".format(
                resource.render, type(result), result))
        elif result is server.NOT_DONE_YET:
            return self.deferred
        else:
            raise ValueError("Unexpected return value: {!r}".format(result))

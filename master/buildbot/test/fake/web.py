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

from StringIO import StringIO
from mock import Mock

from buildbot.status.web import baseweb
from buildbot.test.fake import fakemaster

from twisted.internet import defer
from twisted.web import server


class FakeRequest(Mock):

    """
    A fake Twisted Web Request object, including some pointers to the
    buildmaster and an addChange method on that master which will append its
    arguments to self.addedChanges.
    """

    written = ''
    finished = False
    redirected_to = None
    failure = None

    def __init__(self, args=None, content=''):
        Mock.__init__(self, spec=server.Request)

        if args is None:
            args = {}

        self.args = args
        self.content = StringIO(content)
        self.site = Mock(spec=server.Site)
        webstatus = baseweb.WebStatus(site=self.site)
        self.site.buildbot_service = webstatus
        self.uri = '/'
        self.prepath = []
        self.method = 'GET'
        self.received_headers = {}
        master = webstatus.master = fakemaster.make_master()

        webstatus.setUpJinja2()

        self.addedChanges = []

        def addChange(**kwargs):
            self.addedChanges.append(kwargs)
            return defer.succeed(Mock())
        master.addChange = addChange

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
        result = resource.render(self)
        if isinstance(result, str):
            self.write(result)
            self.finish()
            return self.deferred
        elif result is server.NOT_DONE_YET:
            return self.deferred
        else:
            raise ValueError("Unexpected return value: %r" % (result,))

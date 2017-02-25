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
#
# code inspired/copied from contrib/github_buildbot
#  and inspired from code from the Chromium project
# otherwise, Andrew Melo <andrew.melo@gmail.com> wrote the rest
# but "the rest" is pretty minimal

from __future__ import absolute_import
from __future__ import print_function

import re

from twisted.internet import defer
from twisted.python import log
from twisted.python.reflect import namedModule
from twisted.web import server

from buildbot.util import bytes2NativeString
from buildbot.util import unicode2bytes
from buildbot.www import resource


class ChangeHookResource(resource.Resource):
    # this is a cheap sort of template thingy
    contentType = "text/html; charset=utf-8"
    children = {}
    needsReconfig = True

    def __init__(self, dialects=None, master=None):
        """
        The keys of 'dialects' select a modules to load under
        master/buildbot/www/hooks/
        The value is passed to the module's getChanges function, providing
        configuration options to the dialect.
        """
        resource.Resource.__init__(self, master)

        if dialects is None:
            dialects = {}
        self.dialects = dialects
        self.request_dialect = None

    def reconfigResource(self, new_config):
        self.dialects = new_config.www.get('change_hook_dialects', {})

    def getChild(self, name, request):
        return self

    def render_GET(self, request):
        """
        Responds to events and starts the build process
          different implementations can decide on what methods they will accept
        """
        return self.render_POST(request)

    def render_POST(self, request):
        """
        Responds to events and starts the build process
          different implementations can decide on what methods they will accept

        :arguments:
            request
                the http request object
        """

        try:
            changes, src = self.getChanges(request)
        except ValueError as val_err:
            request.setResponseCode(400, unicode2bytes(val_err.args[0]))
            return unicode2bytes(val_err.args[0])
        except Exception as e:
            log.err(e, "processing changes from web hook")
            msg = b"Error processing changes."
            request.setResponseCode(500, msg)
            return msg

        log.msg("Payload: " + str(request.args))

        if not changes:
            log.msg("No changes found")
            return b"no changes found"
        d = self.submitChanges(changes, request, src)

        def ok(_):
            request.setResponseCode(202)
            request.finish()

        def err(why):
            log.err(why, "adding changes from web hook")
            request.setResponseCode(500)
            request.finish()

        d.addCallbacks(ok, err)

        return server.NOT_DONE_YET

    def getChanges(self, request):
        """
        Take the logic from the change hook, and then delegate it
        to the proper handler
        http://localhost/change_hook/DIALECT will load up
        buildmaster/hooks/DIALECT.py

        and call getChanges()

        the return value is a list of changes

        if DIALECT is unspecified, a sample implementation is provided
        """
        uriRE = re.search(r'^/change_hook/?([a-zA-Z0-9_]*)', bytes2NativeString(request.uri))

        if not uriRE:
            log.msg("URI doesn't match change_hook regex: %s" % request.uri)
            raise ValueError(
                "URI doesn't match change_hook regex: %s" % request.uri)

        changes = []
        src = None

        # Was there a dialect provided?
        if uriRE.group(1):
            dialect = uriRE.group(1)
        else:
            dialect = 'base'

        if dialect in self.dialects:
            log.msg("Attempting to load module buildbot.www.hooks." + dialect)
            tempModule = namedModule('buildbot.www.hooks.' + dialect)
            changes, src = tempModule.getChanges(
                request, self.dialects[dialect])
            log.msg("Got the following changes %s" % changes)
            self.request_dialect = dialect
        else:
            m = "The dialect specified, '%s', wasn't whitelisted in change_hook" % dialect
            log.msg(m)
            log.msg(
                "Note: if dialect is 'base' then it's possible your URL is malformed and we didn't regex it properly")
            raise ValueError(m)

        return (changes, src)

    @defer.inlineCallbacks
    def submitChanges(self, changes, request, src):
        for chdict in changes:
            change = yield self.master.addChange(src=src, **chdict)
            log.msg("injected change %s" % change)

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

import re
from datetime import datetime

from twisted.internet import defer
from twisted.python import log
from twisted.web import server

from buildbot.plugins.db import get_plugins
from buildbot.util import bytes2unicode
from buildbot.util import datetime2epoch
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
        super().__init__(master)

        if dialects is None:
            dialects = {}
        self.dialects = dialects
        self._dialect_handlers = {}
        self.request_dialect = None
        self._plugins = get_plugins("webhooks")

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
            d = self.getAndSubmitChanges(request)
        except Exception:
            d = defer.fail()

        def ok(_):
            request.setResponseCode(202)
            request.finish()

        def err(why):
            code = 500
            if why.check(ValueError):
                code = 400
                msg = unicode2bytes(why.getErrorMessage())
            else:
                log.err(why, "adding changes from web hook")
                msg = b'Error processing changes.'
            request.setResponseCode(code, msg)
            request.write(msg)
            request.finish()

        d.addCallbacks(ok, err)

        return server.NOT_DONE_YET

    @defer.inlineCallbacks
    def getAndSubmitChanges(self, request):
        changes, src = yield self.getChanges(request)
        if not changes:
            request.write(b"no change found")
        else:
            yield self.submitChanges(changes, request, src)
            request.write(unicode2bytes("{} change found".format(len(changes))))

    def makeHandler(self, dialect):
        """create and cache the handler object for this dialect"""
        if dialect not in self.dialects:
            m = "The dialect specified, '{}', wasn't whitelisted in change_hook".format(dialect)
            log.msg(m)
            log.msg(
                "Note: if dialect is 'base' then it's possible your URL is malformed and we didn't regex it properly")
            raise ValueError(m)

        if dialect not in self._dialect_handlers:
            if dialect not in self._plugins:
                m = "The dialect specified, '{}', is not registered as a buildbot.webhook plugin".format(dialect)
                log.msg(m)
                raise ValueError(m)
            options = self.dialects[dialect]
            if isinstance(options, dict) and 'custom_class' in options:
                klass = options['custom_class']
            else:
                klass = self._plugins.get(dialect)
            self._dialect_handlers[dialect] = klass(self.master, self.dialects[dialect])

        return self._dialect_handlers[dialect]

    @defer.inlineCallbacks
    def getChanges(self, request):
        """
        Take the logic from the change hook, and then delegate it
        to the proper handler

        We use the buildbot plugin mechanisms to find out about dialects

        and call getChanges()

        the return value is a list of changes

        if DIALECT is unspecified, a sample implementation is provided
        """
        uriRE = re.search(r'^/change_hook/?([a-zA-Z0-9_]*)', bytes2unicode(request.uri))

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

        handler = self.makeHandler(dialect)
        changes, src = yield handler.getChanges(request)
        return (changes, src)

    @defer.inlineCallbacks
    def submitChanges(self, changes, request, src):
        for chdict in changes:
            when_timestamp = chdict.get('when_timestamp')
            if isinstance(when_timestamp, datetime):
                chdict['when_timestamp'] = datetime2epoch(when_timestamp)
            # unicodify stuff
            for k in ('comments', 'author', 'revision', 'branch', 'category',
                    'revlink', 'repository', 'codebase', 'project'):
                if k in chdict:
                    chdict[k] = bytes2unicode(chdict[k])
            if chdict.get('files'):
                chdict['files'] = [bytes2unicode(f)
                                for f in chdict['files']]
            if chdict.get('properties'):
                chdict['properties'] = dict((bytes2unicode(k), v)
                                            for k, v in chdict['properties'].items())
            chid = yield self.master.data.updates.addChange(src=bytes2unicode(src), **chdict)
            log.msg("injected change %s" % chid)

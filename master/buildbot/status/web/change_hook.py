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

# code inspired/copied from contrib/github_buildbot
#  and inspired from code from the Chromium project
# otherwise, Andrew Melo <andrew.melo@gmail.com> wrote the rest
# but "the rest" is pretty minimal

import re
from twisted.web import resource
from twisted.python.reflect import namedModule
from twisted.python import log
from twisted.internet import defer

class ChangeHookResource(resource.Resource):
     # this is a cheap sort of template thingy
    contentType = "text/html; charset=utf-8"
    children    = {}
    def __init__(self, dialects={}):
        """
        The keys of 'dialects' select a modules to load under
        master/buildbot/status/web/hooks/
        The value is passed to the module's getChanges function, providing
        configuration options to the dialect.
        """
        self.dialects = dialects
    
    def getChild(self, name, request):
        return self

    def render_GET(self, request):
        """
        Reponds to events and starts the build process
          different implementations can decide on what methods they will accept
        """
        return self.render_POST(request)

    def render_POST(self, request):
        """
        Reponds to events and starts the build process
          different implementations can decide on what methods they will accept
        
        :arguments:
            request
                the http request object
        """

        try:
            changes = self.getChanges( request )
        except ValueError, err:
            request.setResponseCode(400, err.args[0])
            return defer.succeed(err.args[0])

        log.msg("Payload: " + str(request.args))
        
        if not changes:
            log.msg("No changes found")
            return defer.succeed("no changes found")
        d = self.submitChanges( changes, request )
        d.addCallback(lambda _ : "OK")
        return d

    
    def getChanges(self, request):
        """
        Take the logic from the change hook, and then delegate it
        to the proper handler
        http://localhost/change_hook/DIALECT will load up
        buildmaster/status/web/hooks/DIALECT.py
        
        and call getChanges()
        
        the return value is a list of changes
        
        if DIALECT is unspecified, a sample implementation is provided
        """
        uriRE = re.search(r'^/change_hook/?([a-zA-Z0-9_]*)', request.uri)
        
        if not uriRE:
            log.msg("URI doesn't match change_hook regex: %s" % request.uri)
            raise ValueError("URI doesn't match change_hook regex: %s" % request.uri)
        
        changes = []
        
        # Was there a dialect provided?
        if uriRE.group(1):
            dialect = uriRE.group(1)
        else:
            dialect = 'base'
            
        if dialect in self.dialects.keys():
            log.msg("Attempting to load module buildbot.status.web.hooks." + dialect)
            tempModule = namedModule('buildbot.status.web.hooks.' + dialect)
            changes = tempModule.getChanges(request,self.dialects[dialect])
            log.msg("Got the following changes %s" % changes)

        else:
            m = "The dialect specified, '%s', wasn't whitelisted in change_hook" % dialect
            log.msg(m)
            log.msg("Note: if dialect is 'base' then it's possible your URL is malformed and we didn't regex it properly")
            raise ValueError(m)

        return changes
                
    @defer.deferredGenerator
    def submitChanges(self, changes, request):
        master = request.site.buildbot_service.master
        for chdict in changes:
            wfd = defer.waitForDeferred(master.addChange(**chdict))
            yield wfd
            change = wfd.getResult()
            log.msg("injected change %s" % change)

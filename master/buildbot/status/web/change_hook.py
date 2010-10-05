# code inspired/copied from contrib/github_buildbot
#  and inspired from code from the Chromium project
# otherwise, Andrew Melo <andrew.melo@gmail.com> wrote the rest

# but "the rest" is pretty minimal
from twisted.web import resource
from buildbot.status.builder import FAILURE
import re
from buildbot import util, interfaces
import traceback
import sys
from buildbot.process.properties import Properties
from buildbot.changes.changes import Change
from twisted.python.reflect import namedModule
from twisted.python.log import msg,err
from buildbot.util import json

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
        except ValueError as err:
            request.setResponseCode(400, err.args[0])
            return err.args[0]

        msg("Payload: " + str(request.args))
        
        if not changes:
            msg("No changes found")
            return "no changes found"
        submitted = self.submitChanges( changes, request )
        return json.dumps(submitted)

    
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
            msg("URI doesn't match change_hook regex: %s" % request.uri)
            raise ValueError("URI doesn't match change_hook regex: %s" % request.uri)
        
        changes = []
        
        # Was there a dialect provided?
        if uriRE.group(1):
            dialect = uriRE.group(1)
        else:
            dialect = 'base'
            
        if dialect in self.dialects.keys():
            msg("Attempting to load module buildbot.status.web.hooks." + dialect)
            tempModule = namedModule('buildbot.status.web.hooks.' + dialect)
            changes = tempModule.getChanges(request,self.dialects[dialect])
            msg("Got the following changes %s" % changes)

        else:
            m = "The dialect specified, '%s', wasn't whitelisted in change_hook" % dialect
            msg(m)
            msg("Note: if dialect is 'base' then it's possible your URL is malformed and we didn't regex it properly")
            raise ValueError(m)

        return changes
                
    def submitChanges(self, changes, request):
        # get a control object
        changeMaster = request.site.buildbot_service.master.change_svc
        submitted = []
        for onechange in changes:
            changeMaster.addChange( onechange )
            d = onechange.asDict()
            msg("injected change %s" % d)
            submitted.append(d)
        return submitted

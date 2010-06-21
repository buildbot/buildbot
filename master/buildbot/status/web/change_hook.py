# code inspired/copied from contrib/github_buildbot
#  and inspired from code from the Chromium project
# otherwise, Andrew Melo <andrew.melo@gmail.com> wrote the rest

# but "the rest" is pretty minimal
from twisted.web import resource
from buildbot.status.builder import FAILURE
import re
from buildbot import util, interfaces
import logging
import traceback
import sys
from buildbot.process.properties import Properties
from buildbot.changes.changes import Change
from twisted.python.reflect import namedModule
try:
    import json
except ImportError:
    import simplejson as json


class ChangeHookResource(resource.Resource):
     # this is a cheap sort of template thingy
    contentType = "text/html; charset=utf-8"
    
    def __init__(self, dialects=None):
        self.dialects = options
    
    def getChild(self, name, request):
        return self

    def render_GET(self, request):
        self.render_POST(request)

    def render_POST(self, request):
        """
        Reponds only to POST events and starts the build process
        
        :arguments:
            request
                the http request object
        """
        try:

            changes = self.getChanges( request )
            logging.debug("Payload: " + str(request.args))
            
            if not changes:
                logging.warning("No changes found")
                return
            self.submitChanges( changes, request )
	    return "changes %s" % changes
        except Exception:
            logging.error("Encountered an exception in change_hook:")
            for msg in traceback.format_exception(*sys.exc_info()):
                logging.error(msg.strip())
	
  
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
            logging.debug("URI doesn't match change_hook regex: %s" % request.uri)
            return
        
        changes = []
        if uriRE.group(1):
            # means we have a dielect in the url
            dialect = uriRE.group(1)
            if dialect in self.dialects.keys():
                try:
                    # note, this should be safe, only alphanumerics and _ are
                    # allowed in the dialect name
                    tempModule = namedModule('buildbot.status.web.hooks.' + dialect)
                    changes = tempModule.getChanges(request,self.dialects[dialect])
                except:
                    logging.error("Encountered an exception in change_hook:")
                    for msg in traceback.format_exception(*sys.exc_info()):
                        logging.error(msg.strip())
            else:
                logging.error("Invalid dialect specified %s" % dialect)
        else:
            if 'DEFAULT' in self.dialects.keys():
                changes = self.getChangesBase(request)

            else:
                logging.error("Tried to use the DEFAULT dialect, but it wasn't whitelisted")
                
        return changes        
                
    def submitChanges(self, changes, request):
        # get a control object
        changeMaster = request.site.buildbot_service.master.change_svc
        for onechange in changes:
            changeMaster.addChange( onechange )
        
    
    def getChangesBase(self, request):
        """
        Consumes a naive build notification (the default for now)
        basically, set POST variables to match commit object parameters:
        revision, revlink, comments, branch, who, files, links
        
        files and links will be de-json'd, the rest are interpreted as strings
        """
        
        def firstOrNothing( value ):
            """
            Small helper function to return the first value (if value is a list)
            or return the whole thing otherwise
            """
            if ( type(value) == type([])):
                return value[0]
            else:
                return value
            
        args = request.args

        # first, convert files and links
        files = None
        if args.get('files'):
            files = json.loads( args.get('files')[0] )
        else:
            files = []
                
        links = None
        if args.get('links'):
            links = json.loads( args.get('links')[0] )
        else:
            links = []
            
        revision = firstOrNothing(args.get('revision'))
        when     = firstOrNothing(args.get('when'))
        who = firstOrNothing(args.get('who'))
        comments = firstOrNothing(args.get('comments'))
        isdir = firstOrNothing(args.get('isdir',0))
        branch = firstOrNothing(args.get('branch'))
        category = firstOrNothing(args.get('category'))
        revlink = firstOrNothing(args.get('revlink'))
        properties = Properties()
        # properties.update(properties, "Change")
        repository = firstOrNothing(args.get('repository'))
        project = firstOrNothing(args.get('project'))
              
        ourchange = Change(who = who, files = files, comments = comments, isdir = isdir, links = links,
                        revision=revision, when = when, branch = branch, category = category,
                        revlink = revlink, repository = repository, project = project)  
	return [ourchange]




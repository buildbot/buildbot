# code inspired/copied from contrib/github_buildbot
#  and inspired from code from the Chromium project
# otherwise, Andrew Melo <andrew.melo@gmail.com> wrote the rest

# but "the rest" is pretty minimal
from buildbot.changes.changes import Change
from buildbot.util import json
    
def getChanges(request, options=None):
        """
        Consumes a naive build notification (the default for now)
        basically, set POST variables to match commit object parameters:
        revision, revlink, comments, branch, who, files, links
        
        files, links and properties will be de-json'd, the rest are interpreted as strings
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

        # first, convert files, links and properties
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

        properties = None
        if args.get('properties'):
            properties = json.loads( args.get('properties')[0] )
        else:
            properties = {}
            
        revision = firstOrNothing(args.get('revision'))
        when     = firstOrNothing(args.get('when'))
        who = firstOrNothing(args.get('who'))
        comments = firstOrNothing(args.get('comments'))
        isdir = firstOrNothing(args.get('isdir',0))
        branch = firstOrNothing(args.get('branch'))
        category = firstOrNothing(args.get('category'))
        revlink = firstOrNothing(args.get('revlink'))
        repository = firstOrNothing(args.get('repository'))
        project = firstOrNothing(args.get('project'))
              
        ourchange = Change(who = who, files = files, comments = comments, isdir = isdir, links = links,
                        revision=revision, when = when, branch = branch, category = category,
                        revlink = revlink, properties = properties, repository = repository,
                        project = project)
        return [ourchange]




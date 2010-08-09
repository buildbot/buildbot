#!/usr/bin/env python
"""
github_buildbot.py is based on git_buildbot.py

github_buildbot.py will determine the repository information from the JSON 
HTTP POST it receives from github.com and build the appropriate repository.
If your github repository is private, you must add a ssh key to the github
repository for the user who initiated the build on the buildslave.

"""

import tempfile
import logging
import re
import sys
import traceback
from twisted.web import server, resource
from twisted.internet import reactor
from twisted.spread import pb
from twisted.cred import credentials
from optparse import OptionParser
from buildbot.changes.changes import Change
import datetime
import time
from twisted.python.log import msg,err
import calendar

try:
    import json
except ImportError:
    import simplejson as json

def getChanges(request, options = None):
        """
        Reponds only to POST events and starts the build process
        
        :arguments:
            request
                the http request object
        """
        try:
            payload = json.loads(request.args['payload'][0])
            user = payload['repository']['owner']['name']
            repo = payload['repository']['name']
            repo_url = payload['repository']['url']
            private = payload['repository']['private']
            logging.debug("Payload: " + str(payload))
            changes = process_change(payload, user, repo, repo_url)
            err("Changes: %s" % changes)
            return changes
        except Exception:
            logging.error("Encountered an exception:")
            for msg in traceback.format_exception(*sys.exc_info()):
                logging.error(msg.strip())

def process_change(payload, user, repo, repo_url):
        """
        Consumes the JSON as a python object and actually starts the build.
        
        :arguments:
            payload
                Python Object that represents the JSON sent by GitHub Service
                Hook.
        """
        changes = []
        newrev = payload['after']
        refname = payload['ref']
        msg( "in process_change" )
        # We only care about regular heads, i.e. branches
        match = re.match(r"^refs\/heads\/(.+)$", refname)
        if not match:
            logging.info("Ignoring refname `%s': Not a branch" % refname)

        branch = match.group(1)
        # Find out if the branch was created, deleted or updated. Branches
        # being deleted aren't really interesting.
#        {"removed":[],
#        "modified":["setup.py"],
#        "message":"Give some polite messages when trying to run lint/coverage without the modules being installed.",
#        "added":[],
#        "url":"http://github.com/PerilousApricot/WMCore/commit/71f79484bde30a1d2067719e13df8212c4032c2e",
#        "timestamp":"2010-01-12T05:02:37-08:00",
#        "id":"71f79484bde30a1d2067719e13df8212c4032c2e",
#        "author":{"email":"metson","name":"metson"}}

        if re.match(r"^0*$", newrev):
            msg("Branch `%s' deleted, ignoring" % branch)
            return []
        else: 
            for commit in payload['commits']:
                files = []
                files.extend(commit['added'])
                files.extend(commit['modified'])
                files.extend(commit['removed'])
                # you know what sucks? this. converting
                # from the github provided time to a unix timestamp
                # python2.4 doesn't have the %z argument to strptime
                # which means it won't accept a numeric timezone offset
                
                # first make a UTC-esque timestamp
                #  do this in 2 steps, first, convert the timestamp directly
                #    to UTC (i.e. 1970-01-01T00:00:00 is zero, regardless of
                #    the local timezone )
                err("Timestamp is %s" % commit['timestamp'])
                when =  calendar.timegm(time.strptime(\
                                     (commit['timestamp'][:-6] + ' UTC'),\
                                    "%Y-%m-%dT%H:%M:%S %Z"))
                # when is now a timestamp if we were at UTC
                err("UTC when is %s" % str(when))
                err("When astext is %s" % time.gmtime(int(when)))
                # shift the time according to the offset in the timestamp
                hourShift    = commit['timestamp'][-5:-3]
                minShift     = commit['timestamp'][-2:]
                totalSeconds = int(hourShift) * 60 * 60 + int(minShift) *60
                err("hour %s min %s shift %s" % (hourShift, minShift, totalSeconds))
                if commit['timestamp'][-6] == '+':
                    when = str(float(when) + int(totalSeconds))
                elif commit['timestamp'][-6] == '-':
                    when = str(float(when) - int(totalSeconds))
                else:
                    raise RuntimeError, "Unknown timestamp from github"
                
                # now, when is a string of the number of seconds from UTC
                # epoch. Take those seconds and make a local time out of it
                localWhen        = time.localtime(float(when))
                err("localwhen is %s" % localWhen)
                localPosixOffset = time.mktime(localWhen)
                err("offset from utcwhen is %s" % (localPosixOffset - float(when)))
                change = {'revision': commit['id'],
                     'revlink': commit['url'],
                     'comments': commit['message'],
                     'branch': branch,
                     'who': commit['author']['name'] 
                            + " <" + commit['author']['email'] + ">",
                     'files': files,
                     'links': [commit['url']],
                     'properties': {'repository': repo_url},
                }
    
                logging.info("New revision: %s" % change['revision'][:8])
                for key, value in change.iteritems():
                    logging.debug("  %s: %s" % (key, value))
                changeObject = Change(\
                        who      = commit['author']['name'] 
                                    + " <" + commit['author']['email'] + ">",
                        files    = files,
                        comments = commit['message'], 
                        links    = [commit['url']],
                        revision = commit['id'],
                        when     = localPosixOffset,
                        branch   = branch,
                        revlink  = commit['url'], 
                        repository = repo_url)  
                changes.append(changeObject) 
            return changes
        

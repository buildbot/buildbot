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

#!/usr/bin/env python
"""
bitbucket.py is based on github.py

bitbucket.py will determine the repository information from the JSON 
HTTP POST it receives from bitbucket.org and build the appropriate repository.

The POST format is specified here: https://confluence.atlassian.com/display/BITBUCKET/POST+Service+Management
"""

import re
import datetime
from twisted.python import log
import calendar

try:
    import json
    assert json
except ImportError:
    import simplejson as json

# python is silly about how it handles timezones
class fixedOffset(datetime.tzinfo):
    """
    fixed offset timezone
    """
    def __init__(self, minutes, hours, offsetSign = 1):
        self.minutes = int(minutes) * offsetSign
        self.hours   = int(hours)   * offsetSign
        self.offset  = datetime.timedelta(minutes = self.minutes,
                                         hours   = self.hours)

    def utcoffset(self, dt):
        return self.offset

    def dst(self, dt):
        return datetime.timedelta(0)
    
def convertTime(myTestTimestamp):
    #"2012-05-30 04:07:03+00:00"
    matcher = re.compile(r'(\d\d\d\d)-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)([-+\s])(\d\d):(\d\d)')
    result  = matcher.match(myTestTimestamp)
    if result is None:
        matcher = re.compile(r'(\d\d\d\d)-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)([-+])(\d\d):(\d\d)')
    result  = matcher.match(myTestTimestamp)
    (year, month, day, hour, minute, second, offsetsign, houroffset, minoffset) = \
        result.groups()
    if offsetsign == '-':
        offsetsign = -1
    else:
        offsetsign = 1
    
    offsetTimezone = fixedOffset( minoffset, houroffset, offsetsign )
    myDatetime = datetime.datetime( int(year),
                                    int(month),
                                    int(day),
                                    int(hour),
                                    int(minute),
                                    int(second),
                                    0,
                                    offsetTimezone)
    return calendar.timegm( myDatetime.utctimetuple() )

def getChanges(request, options = None):
        """
        Reponds only to POST events and starts the build process
        
        :arguments:
            request
                the http request object
        """
        log.msg("Received POST from Bitbucket: %s" % str(request.args))
        payload = json.loads(request.args['payload'][0])
        user = payload['repository']['owner']
        repo = payload['repository']['name']
        repo_url = payload["canon_url"]+payload['repository']['absolute_url']
        project = request.args.get('project', None)
        if project:
            project = project[0]
        elif project is None:
            project = ''
        changes = process_change(payload, user, repo, repo_url, project)
        log.msg("Received %s changes from bitbucket" % len(changes))
        
        return (changes, payload['repository']['scm'])

def process_change(payload, user, repo, repo_url, project):
        """
        Consumes the JSON as a python object and actually starts the build.
        
        :arguments:
            payload
                Python Object that represents the JSON sent by Bitbucket Service
                Hook.
        """
        changes = []
        for commit in payload['commits']:
            files = []
            for f in commit['files']:
                files.append(f['file'])
            when =  convertTime( commit['utctimestamp'])
            log.msg("New revision: %s" % commit['node'])
            chdict = dict(
                who      = commit['raw_author'],
                files    = files,
                comments = commit['message'], 
                revision = commit['raw_node'],
                when     = when,
                branch   = commit['branch'],
                revlink  = repo_url + commit['raw_node'], 
                repository = repo_url,
                project  = project)
            changes.append(chdict) 
        return changes
        

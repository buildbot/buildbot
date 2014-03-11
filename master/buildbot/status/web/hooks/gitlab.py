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

from buildbot.status.web.hooks.github import process_change
from buildbot.util import json
from twisted.python import log


def getChanges(request, options=None):
    """
    Reponds only to POST events and starts the build process

    :arguments:
        request
            the http request object
    """
    try:
        payload = json.load(request.content)
    except Exception, e:
        raise ValueError("Error loading JSON: " + str(e))
    user = payload['user_name']
    repo = payload['repository']['name']
    repo_url = payload['repository']['url']
    raw_project = request.args.get('project', None)
    project = raw_project[0] if raw_project is not None else ''
    codebase = request.args.get('codebase', None)
    if codebase:
        codebase = codebase[0]
    # This field is unused:
    #private = payload['repository']['private']
    changes = process_change(payload, user, repo, repo_url, project, codebase=codebase)
    log.msg("Received %s changes from gitlab" % len(changes))
    return (changes, 'git')

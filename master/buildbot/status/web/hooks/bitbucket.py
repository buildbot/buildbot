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
# Copyright 2013 (c) Mamba Team

try:
    import json
    assert json
except ImportError:
    import simplejson as json

from dateutil.parser import parse as dateparse

from twisted.python import log


def getChanges(request, options=None):
    """Catch a POST request from BitBucket and start a build process

    Check the URL below if you require more information about payload
    https://confluence.atlassian.com/display/BITBUCKET/POST+Service+Management

    :param request: the http request Twisted object
    :param options: additional options
    """

    payload = json.loads(request.args['payload'][0])
    repo_url = '%s%s' % (
        payload['canon_url'], payload['repository']['absolute_url'])
    project = (
        request.args.get('project') if request.args.get('project') is not None
        else ''
    )

    changes = []
    for commit in payload['commits']:
        changes.append({
            'author': commit['raw_author'],
            'files': [f['file'] for f in commit['files']],
            'comments': commit['message'],
            'revision': commit['raw_node'],
            'when_timestamp': dateparse(commit['utctimestamp']),
            'branch': commit['branch'],
            'revlink': '%s%s' % (repo_url, commit['raw_node']),
            'repository': repo_url,
            'project': project
        })
        log.msg('New revision: %s' % (commit['node'],))

    log.msg('Received %s changes from bitbucket' % (len(changes),))
    return (changes, payload['repository']['scm'])

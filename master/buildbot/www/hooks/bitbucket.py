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
import hmac
import logging
import re
from hashlib import sha1

from dateutil.parser import parse as dateparse

from twisted.python import log

try:
    import json
    assert json
except ImportError:
    import simplejson as json


_HEADER_CT = 'Content-Type'
_HEADER_EVENT = 'X-Event-Key'


class BitbucketEventHandler(object):

    def __init__(self, codebase=None):
        self._codebase = codebase

    def process(self, request):
        """
        Process a webhook event request.

        See example on https://developer.atlassian.com/bitbucket/api/2/reference/resource/repositories/%7Busername%7D/%7Brepo_slug%7D/hooks
        for list of all the different events.
        """
        payload = self._get_payload(request)
        event_type = request.getHeader(_HEADER_EVENT)
        log.msg("Processing event %s: %r" % (_HEADER_EVENT, event_type,), logLevel=logging.DEBUG)
        event_type = event_type.replace(":", "_")
        handler = getattr(self, 'handle_%s' % event_type, None)

        if handler is None:
            raise ValueError('Unknown event: %r' % (event_type,))

        return handler(payload)

    def _get_payload(self, request):
        content = request.content.read()
        content_type = request.getHeader(_HEADER_CT)

        if content_type == 'application/json':
            payload = json.loads(content)
        elif content_type == 'application/x-www-form-urlencoded':
            payload = json.loads(request.args['payload'][0])
        else:
            raise ValueError('Unknown content type: %r' % (content_type,))

        log.msg("Payload: %r" % payload, logLevel=logging.DEBUG)

        return payload

    def handle_repo_push(self, payload):
        repo = payload['repository']
        project = repo['name']
        push = payload['push']
        payload['ref'] = push['changes'][0]["new"]["name"]
        repo_url = "git@bitbucket.org:%s.git" % payload['repository']['full_name']  # TOFIX: Hard coded as clone URL is not available
        changes = self._process_change(payload, repo, repo_url, project)
        log.msg("Received %d changes from Bitbucket" % len(changes))
        return changes, 'git'

    def handle_pullrequest_updated(self, payload):
        return self.handle_pullrequest(payload, 'updated_on')

    def handle_pullrequest_created(self, payload):
        return self.handle_pullrequest(payload, 'created_on')


    def _process_change(self, payload, repo, repo_url, project):
        """
        Consumes the JSON as a python object and returns the changes.

        :arguments:
            payload
                Python Object that represents the JSON sent by Bitbucket Webhook event.
        """
        changes = []

        # TOFIX: Code from github hook code, is this functionality needed?
        #refname = payload['ref']
        #
        # We only care about regular heads, i.e. branches
        #match = re.match(r"^refs/heads/(.+)$", refname)
        #print "match:", match
        #if not match:
        #    log.msg("Ignoring refname `%s': Not a branch" % refname)
        #    return changes
        #

        for change_ in payload['push']['changes']:
            if change_['new'] == None:
                # Branch deleted
                continue
            branch = change_['new']['name']
            when_timestamp = dateparse(change_['new']['target']['date'])
            for commit in change_['commits']:
                log.msg("New revision: %s" % commit['hash'][:8])

                change = {
                    'author': '%s <%s>' % (commit['author']['user']['display_name'], commit['author']['user']['username']),
                    'comments': commit['message'],
                    'revision': commit['hash'],
                    'when_timestamp': when_timestamp,
                    'branch': branch,
                    'revlink': commit['links']['html']['href'],
                    'repository': repo_url, # The clone URL used to match in change filter
                    'project': project,
                    'properties': {}
                }

                if callable(self._codebase):
                    change['codebase'] = self._codebase(payload)
                elif self._codebase is not None:
                    change['codebase'] = self._codebase

                changes.append(change)

        return changes

    def handle_pullrequest(self, payload, timestamp_key):
        changes = []
        pr_number = payload["pullrequest"]['id']
        refname = 'refs/pull/%d/merge' % (pr_number,)  # TOFIX: This is from github hook code, someone verify if this makes sense.
        repo_url = "git@bitbucket.org:%s.git" % payload['repository']['full_name']

        log.msg('Processing Bitbucket PR #%d' % pr_number, logLevel=logging.DEBUG)

        change = {
            'revision': payload['pullrequest']['source']['commit']['hash'],
            'when_timestamp': dateparse(payload['pullrequest'][timestamp_key]),
            'branch': refname,
            'revlink': payload['pullrequest']['links']['commits']['href'],
            'repository': repo_url, # The clone URL used to match in change filter
            'project': payload['repository']['project']['name'],
            'category': 'pull',
            'author': '%s <%s>' % (payload['pullrequest']['author']['display_name'],
                                   payload['pullrequest']['author']['username']),
            'comments': 'Bitbucket Pull Request #%d' % (pr_number, ),
        }

        if callable(self._codebase):
            change['codebase'] = self._codebase(payload)
        elif self._codebase is not None:
            change['codebase'] = self._codebase

        changes.append(change)

        log.msg("Received %d changes from Bitbucket PR #%d" % (
            len(changes), pr_number))
        return changes, 'git'


def processPostService(request, options=None):
    """Catch a POST service request from BitBucket and start a build process

    Check the URL below if you require more information about payload
    https://confluence.atlassian.com/display/BITBUCKET/POST+Service+Management

    :param request: the http request Twisted object
    :param options: additional options
    """
    payload = json.loads(request.args['payload'][0])
    repo_url = '%s%s' % (
        payload['canon_url'], payload['repository']['absolute_url'])
    project = request.args.get('project', [''])[0]

    changes = []
    for commit in payload['commits']:
        changes.append({
            'author': commit['raw_author'],
            'files': [f['file'] for f in commit['files']],
            'comments': commit['message'],
            'revision': commit['raw_node'],
            'when_timestamp': dateparse(commit['utctimestamp']),
            'branch': commit['branch'],
            'revlink': '%scommits/%s' % (repo_url, commit['raw_node']),
            'repository': repo_url,
            'project': project
        })
        log.msg('New revision: %s' % (commit['node'],))

    log.msg('Received %s changes from bitbucket' % (len(changes),))
    return (changes, payload['repository']['scm'])


def getChanges(request, options=None):
    """
    Process the Bitbucket webhook event.

    :arguments:
        request
            the http request object
    """
    if type(options) is not dict:
        options = {}

    if 'payload' in request.args:
        return processPostService(request)

    klass = options.get('class', BitbucketEventHandler)

    handler = klass(options.get('codebase', None))
    return handler.process(request)

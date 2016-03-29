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
# Copyright 2011, Louis Opter <kalessin@kalessin.fr>
#
# Quite inspired from the github hook.
import hmac

from twisted.python import log

from buildbot.util import json


class GoogleCodeAuthFailed(Exception):
    pass


class Payload(object):

    def __init__(self, headers, body, branch):
        self._auth_code = headers['Google-Code-Project-Hosting-Hook-Hmac']
        self._body = body  # we need to save it if we want to authenticate it
        self._branch = branch

        payload = json.loads(body)
        self.project = payload['project_name']
        self.repository = payload['repository_path']
        self.revisions = payload['revisions']
        self.revision_count = payload['revision_count']

    def authenticate(self, secret_key):
        m = hmac.new(secret_key)
        m.update(self._body)
        digest = m.hexdigest()
        return digest == self._auth_code

    def changes(self):
        changes = []

        for r in self.revisions:
            files = set()
            files.update(r['added'])
            files.update(r['modified'])
            files.update(r['removed'])
            changes.append(dict(
                author=r['author'],
                files=list(files),
                comments=r['message'],
                revision=r['revision'],
                when=r['timestamp'],
                # Let's hope Google add the branch one day:
                branch=r.get('branch', self._branch),
                revlink=r['url'],
                repository=self.repository,
                project=self.project
            ))

        return changes


def getChanges(request, options=None):
    headers = request.received_headers
    body = request.content.getvalue()

    # Instantiate a Payload object: this will parse the body, get the
    # authentication code from the headers and remember the branch picked
    # up by the user (Google Code doesn't send on which branch the changes
    # were made)
    payload = Payload(headers, body, options.get('branch', 'default'))

    if 'secret_key' in options:
        if not payload.authenticate(options['secret_key']):
            raise GoogleCodeAuthFailed()
    else:
        log.msg("Missing secret_key in the Google Code WebHook options: "
                "cannot authenticate the request!")

    log.msg('Received %d changes from Google Code' %
            (payload.revision_count,))
    changes = payload.changes()

    return changes, 'Google Code'

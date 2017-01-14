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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import traceback

from twisted.internet import defer

from buildbot.clients import sendchange as sendchange_client
from buildbot.util import in_reactor


@in_reactor
@defer.inlineCallbacks
def sendchange(config):
    encoding = config.get('encoding', 'utf8')
    who = config.get('who')
    auth = config.get('auth')
    master = config.get('master')
    branch = config.get('branch')
    category = config.get('category')
    revision = config.get('revision')
    properties = config.get('properties', {})
    repository = config.get('repository', '')
    vc = config.get('vc', None)
    project = config.get('project', '')
    revlink = config.get('revlink', '')
    when = config.get('when')
    comments = config.get('comments')
    files = config.get('files', ())
    codebase = config.get('codebase', None)

    s = sendchange_client.Sender(master, auth, encoding=encoding)
    try:
        yield s.send(branch, revision, comments, files, who=who,
                     category=category, when=when, properties=properties,
                     repository=repository, vc=vc, project=project, revlink=revlink,
                     codebase=codebase)
    except Exception:
        print("change not sent:")
        traceback.print_exc(file=sys.stdout)
        defer.returnValue(1)
    else:
        print("change sent successfully")
        defer.returnValue(0)

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
from __future__ import print_function

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import patches
from buildbot.data import types


def _db2data(ss):
    data = {
        'ssid': ss['ssid'],
        'branch': ss['branch'],
        'revision': ss['revision'],
        'project': ss['project'],
        'repository': ss['repository'],
        'codebase': ss['codebase'],
        'created_at': ss['created_at'],
        'patch': None,
    }
    if ss['patch_body']:
        data['patch'] = {
            'patchid': ss['patchid'],
            'level': ss['patch_level'],
            'subdir': ss['patch_subdir'],
            'author': ss['patch_author'],
            'comment': ss['patch_comment'],
            'body': ss['patch_body'],
        }
    return data


class SourceStampEndpoint(base.Endpoint):

    isCollection = False
    pathPatterns = """
        /sourcestamps/n:ssid
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        ssdict = yield self.master.db.sourcestamps.getSourceStamp(
            kwargs['ssid'])
        defer.returnValue(_db2data(ssdict) if ssdict else None)


class SourceStampsEndpoint(base.Endpoint):

    isCollection = True
    pathPatterns = """
        /sourcestamps
    """
    rootLinkName = 'sourcestamps'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        defer.returnValue([_db2data(ssdict) for ssdict in
                           (yield self.master.db.sourcestamps.getSourceStamps())])


class SourceStamp(base.ResourceType):

    name = "sourcestamp"
    plural = "sourcestamps"
    endpoints = [SourceStampEndpoint, SourceStampsEndpoint]
    keyFields = ['ssid']

    class EntityType(types.Entity):
        ssid = types.Integer()
        revision = types.NoneOk(types.String())
        branch = types.NoneOk(types.String())
        repository = types.String()
        project = types.String()
        codebase = types.String()
        patch = types.NoneOk(patches.Patch.entityType)
        created_at = types.DateTime()
    entityType = EntityType(name)

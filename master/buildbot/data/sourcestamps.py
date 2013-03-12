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

from twisted.internet import defer
from buildbot.data import base
from buildbot.util import datetime2epoch

def _db2data(ss):
    data = {
        'ssid': ss['ssid'],
        'branch': ss['branch'],
        'revision': ss['revision'],
        'project': ss['project'],
        'repository': ss['repository'],
        'codebase': ss['codebase'],
        'created_at': datetime2epoch(ss['created_at']),
        'link': base.Link(('sourcestamp', str(ss['ssid']))),
        'patch': None,
    }
    if ss['patch_body']:
        data['patch'] = {
            'level' : ss['patch_level'],
            'subdir' : ss['patch_subdir'],
            'author' : ss['patch_author'],
            'comment' : ss['patch_comment'],
            'body' : ss['patch_body'],
        }
    return data


class SourceStampEndpoint(base.Endpoint):

    pathPatterns = """
        /sourcestamp/i:ssid
    """

    @defer.inlineCallbacks
    def get(self, options, kwargs):
        ssdict = yield self.master.db.sourcestamps.getSourceStamp(
                                                        kwargs['ssid'])
        defer.returnValue(_db2data(ssdict) if ssdict else None)


class SourceStampsEndpoint(base.GetParamsCheckMixin, base.Endpoint):

    pathPatterns = """
        /sourcestamp
    """
    rootLinkName = 'sourcestamps'

    @defer.inlineCallbacks
    def safeGet(self, options, kwargs):
        defer.returnValue([ _db2data(ssdict) for ssdict in
            (yield self.master.db.sourcestamps.getSourceStamps()) ])

    def startConsuming(self, callback, options, kwargs):
        return self.master.mq.startConsuming(callback,
                ('sourcestamp', None, None))


class SourceStampResourceType(base.ResourceType):

    type = "sourcestamp"
    endpoints = [ SourceStampEndpoint, SourceStampsEndpoint ]
    keyFields = [ 'ssid' ]

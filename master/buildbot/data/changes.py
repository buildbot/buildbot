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
from twisted.python import log
import datetime
from buildbot.data import base, exceptions
from buildbot.process import metrics
from buildbot.process.users import users
from buildbot.util import datetime2epoch, epoch2datetime

class ChangeEndpoint(base.Endpoint):

    pathPattern = ( 'change', 'i:changeid' )

    def get(self, options, kwargs):
        d = self.master.db.changes.getChange(kwargs['changeid'])
        d.addCallback(_fixChange)
        return d


class ChangesEndpoint(base.Endpoint):

    pathPattern = ( 'change', )
    rootLinkName = 'changes'

    def get(self, options, kwargs):
        try:
            count = min(int(options.get('count', '50')), 50)
        except:
            return defer.fail(
                    exceptions.InvalidOptionException('invalid count option'))
        d = self.master.db.changes.getRecentChanges(count)
        @d.addCallback
        def sort(changes):
            changes.sort(key=lambda chdict : chdict['changeid'])
            return map(_fixChange, changes)
        return d

    def startConsuming(self, callback, options, kwargs):
        return self.master.mq.startConsuming(callback,
                ('change', None, 'new'))


class ChangeResourceType(base.ResourceType):

    type = "change"
    endpoints = [ ChangeEndpoint, ChangesEndpoint ]
    keyFields = [ 'changeid' ]

    @base.updateMethod
    @defer.inlineCallbacks
    def addChange(self, files=None, comments=None, author=None, revision=None,
            when_timestamp=None, branch=None, category=None, revlink=u'',
            properties={}, repository=u'', codebase=None, project=u'',
            src=None):
        metrics.MetricCountEvent.log("added_changes", 1)

        # add the source to the properties
        for k in properties:
            properties[k] = (properties[k], u'Change')

        if src:
            # create user object, returning a corresponding uid
            uid = yield users.createUserObject(self.master,
                    author, src)
        else:
            uid = None
        if isinstance(when_timestamp, datetime.datetime):
            when_timestamp = datetime2epoch(when_timestamp)
        change = {
            'changeid': None, # not known yet
            'author': author,
            'files': files,
            'comments': comments,
            'revision': revision,
            'when_timestamp': when_timestamp,
            'branch': branch,
            'category': category,
            'revlink': revlink,
            'properties': properties,
            'repository': repository,
            'project': project,
            'codebase': None, # not set yet
            # 'uid': uid, -- not in data API yet?
        }

        # if the codebase is default, and 
        if codebase is None \
                and self.master.config.codebaseGenerator is not None:
            codebase = self.master.config.codebaseGenerator(change)
            change['codebase'] = unicode(codebase)
        else:
            change['codebase'] = codebase or u''

        # add the Change to the database and notify, converting briefly
        # to database format, then back, and adding the changeid
        del change['changeid']
        change['when_timestamp'] = epoch2datetime(change['when_timestamp'])
        changeid = yield self.master.db.changes.addChange(uid=uid, **change)
        change['when_timestamp'] = datetime2epoch(change['when_timestamp'])
        change['changeid'] = changeid
        self.produceEvent(change, 'new')

        # log, being careful to handle funny characters
        msg = u"added change with revision %s to database" % (revision,)
        log.msg(msg.encode('utf-8', 'replace'))

        defer.returnValue(changeid)


def _fixChange(change):
    # TODO: make these mods in the DB API
    if change:
        change = change.copy()
        del change['is_dir']
        change['when_timestamp'] = datetime2epoch(change['when_timestamp'])
        change['link'] = base.Link(('change', str(change['changeid'])))
    return change

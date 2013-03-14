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

import copy
from twisted.internet import defer, reactor
from twisted.python import log
from buildbot.data import base
from buildbot.process import metrics
from buildbot.process.users import users
from buildbot.util import datetime2epoch, epoch2datetime

class FixerMixin(object):
    @defer.inlineCallbacks
    def _fixChange(self, change):
        # TODO: make these mods in the DB API
        if change:
            change = change.copy()
            del change['is_dir']
            change['when_timestamp'] = datetime2epoch(change['when_timestamp'])
            change['link'] = base.Link(('change', str(change['changeid'])))

            sskey = ('sourcestamp', str(change['sourcestampid']))
            change['sourcestamp'] = yield self.master.data.get({}, sskey)
            del change['sourcestampid']
        defer.returnValue(change)

class ChangeEndpoint(FixerMixin, base.Endpoint):

    pathPatterns = """
        /change/n:changeid
    """

    def get(self, options, kwargs):
        d = self.master.db.changes.getChange(kwargs['changeid'])
        d.addCallback(self._fixChange)
        return d


class ChangesEndpoint(FixerMixin, base.GetParamsCheckMixin, base.Endpoint):

    pathPatterns = """
        /change
    """
    rootLinkName = 'change'
    maximumCount = 50

    @defer.inlineCallbacks
    def safeGet(self, options, kwargs):
        options['total'] = yield self.master.db.changes.getChangesCount(options)
        changes = yield self.master.db.changes.getChanges(options)
        changes = [ (yield self._fixChange(ch)) for ch in changes ]
        defer.returnValue(changes)

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
            src=None, _reactor=reactor):
        metrics.MetricCountEvent.log("added_changes", 1)

        # add the source to the properties
        for k in properties:
            properties[k] = (properties[k], u'Change')

        # get a user id
        if src:
            # create user object, returning a corresponding uid
            uid = yield users.createUserObject(self.master,
                    author, src)
        else:
            uid = None

        # set the codebase, either the default, supplied, or generated
        if codebase is None \
                and self.master.config.codebaseGenerator is not None:
            pre_change = {
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
                'codebase': None,
                # 'uid': uid, -- not in data API yet?
            }
            codebase = self.master.config.codebaseGenerator(pre_change)
            codebase = unicode(codebase)
        else:
            codebase = codebase or u''

        # add the Change to the database 
        changeid = yield self.master.db.changes.addChange(
            author=author,
            files=files,
            comments=comments,
            revision=revision,
            when_timestamp=epoch2datetime(when_timestamp),
            branch=branch,
            category=category,
            revlink=revlink,
            properties=properties,
            repository=repository,
            codebase=codebase,
            project=project,
            uid=uid,
            _reactor=_reactor)

        # get the change and munge the result for the notification
        change = yield self.master.data.get({}, ('change', str(changeid)))
        change = copy.deepcopy(change)
        del change['link']
        del change['sourcestamp']['link']
        self.produceEvent(change, 'new')

        # log, being careful to handle funny characters
        msg = u"added change with revision %s to database" % (revision,)
        log.msg(msg.encode('utf-8', 'replace'))

        defer.returnValue(changeid)

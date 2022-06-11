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
import json

from twisted.internet import defer
from twisted.python import log

from buildbot.data import base
from buildbot.data import sourcestamps
from buildbot.data import types
from buildbot.process import metrics
from buildbot.process.users import users
from buildbot.util import datetime2epoch
from buildbot.util import epoch2datetime


class FixerMixin:

    @defer.inlineCallbacks
    def _fixChange(self, change, is_graphql):
        # TODO: make these mods in the DB API
        if change:
            change = change.copy()
            change['when_timestamp'] = datetime2epoch(change['when_timestamp'])
            if is_graphql:
                props = change['properties']
                change['properties'] = [
                    {'name': k, 'source': v[1], 'value': json.dumps(v[0])}
                    for k, v in props.items()
                ]
            else:
                sskey = ('sourcestamps', str(change['sourcestampid']))
                change['sourcestamp'] = yield self.master.data.get(sskey)
                del change['sourcestampid']
        return change
    fieldMapping = {
        'changeid': 'changes.changeid',
    }


class ChangeEndpoint(FixerMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /changes/n:changeid
    """

    def get(self, resultSpec, kwargs):
        d = self.master.db.changes.getChange(kwargs['changeid'])
        d.addCallback(self._fixChange, is_graphql='graphql' in kwargs)
        return d


class ChangesEndpoint(FixerMixin, base.BuildNestingMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /changes
        /builders/n:builderid/builds/n:build_number/changes
        /builds/n:buildid/changes
        /sourcestamps/n:ssid/changes
    """
    rootLinkName = 'changes'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        buildid = kwargs.get('buildid')
        if 'build_number' in kwargs:
            buildid = yield self.getBuildid(kwargs)
        ssid = kwargs.get('ssid')
        if buildid is not None:
            changes = yield self.master.db.changes.getChangesForBuild(buildid)
        elif ssid is not None:
            change = yield self.master.db.changes.getChangeFromSSid(ssid)
            if change is not None:
                changes = [change]
            else:
                changes = []
        else:
            if resultSpec is not None:
                resultSpec.fieldMapping = self.fieldMapping
                changes = yield self.master.db.changes.getChanges(resultSpec=resultSpec)
        results = []
        for ch in changes:
            results.append((yield self._fixChange(ch, is_graphql='graphql' in kwargs)))
        return results


class Change(base.ResourceType):

    name = "change"
    plural = "changes"
    endpoints = [ChangeEndpoint, ChangesEndpoint]
    eventPathPatterns = """
        /changes/:changeid
    """
    keyField = "changeid"
    subresources = ["Build", "Property"]

    class EntityType(types.Entity):
        changeid = types.Integer()
        parent_changeids = types.List(of=types.Integer())
        author = types.String()
        committer = types.String()
        files = types.List(of=types.String())
        comments = types.String()
        revision = types.NoneOk(types.String())
        when_timestamp = types.Integer()
        branch = types.NoneOk(types.String())
        category = types.NoneOk(types.String())
        revlink = types.NoneOk(types.String())
        properties = types.SourcedProperties()
        repository = types.String()
        project = types.String()
        codebase = types.String()
        sourcestamp = sourcestamps.SourceStamp.entityType
    entityType = EntityType(name, 'Change')

    @base.updateMethod
    @defer.inlineCallbacks
    def addChange(self, files=None, comments=None, author=None, committer=None, revision=None,
                  when_timestamp=None, branch=None, category=None, revlink='',
                  properties=None, repository='', codebase=None, project='',
                  src=None):
        metrics.MetricCountEvent.log("added_changes", 1)

        if properties is None:
            properties = {}
        # add the source to the properties
        for k in properties:
            properties[k] = (properties[k], 'Change')

        # get a user id
        if src:
            # create user object, returning a corresponding uid
            uid = yield users.createUserObject(self.master,
                                               author, src)
        else:
            uid = None

        if not revlink and revision and repository and callable(self.master.config.revlink):
            # generate revlink from revision and repository using the configured callable
            revlink = self.master.config.revlink(revision, repository) or ''

        if callable(category):
            pre_change = self.master.config.preChangeGenerator(author=author,
                                                               committer=committer,
                                                               files=files,
                                                               comments=comments,
                                                               revision=revision,
                                                               when_timestamp=when_timestamp,
                                                               branch=branch,
                                                               revlink=revlink,
                                                               properties=properties,
                                                               repository=repository,
                                                               project=project)
            category = category(pre_change)

        # set the codebase, either the default, supplied, or generated
        if codebase is None \
                and self.master.config.codebaseGenerator is not None:
            pre_change = self.master.config.preChangeGenerator(author=author,
                                                               committer=committer,
                                                               files=files,
                                                               comments=comments,
                                                               revision=revision,
                                                               when_timestamp=when_timestamp,
                                                               branch=branch,
                                                               category=category,
                                                               revlink=revlink,
                                                               properties=properties,
                                                               repository=repository,
                                                               project=project)
            codebase = self.master.config.codebaseGenerator(pre_change)
            codebase = str(codebase)
        else:
            codebase = codebase or ''

        # add the Change to the database
        changeid = yield self.master.db.changes.addChange(
            author=author,
            committer=committer,
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
            uid=uid)

        # get the change and munge the result for the notification
        change = yield self.master.data.get(('changes', str(changeid)))
        change = copy.deepcopy(change)
        self.produceEvent(change, 'new')

        # log, being careful to handle funny characters
        msg = f"added change with revision {revision} to database"
        log.msg(msg.encode('utf-8', 'replace'))

        return changeid

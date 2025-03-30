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

from __future__ import annotations

import copy
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable

from twisted.internet import defer
from twisted.python import log

from buildbot.data import base
from buildbot.data import sourcestamps
from buildbot.data import types
from buildbot.process import metrics
from buildbot.process.users import users
from buildbot.util import datetime2epoch
from buildbot.util import epoch2datetime

if TYPE_CHECKING:
    from buildbot.db.changes import ChangeModel


class FixerMixin:
    @defer.inlineCallbacks
    def _fixChange(self, model: ChangeModel):
        # TODO: make these mods in the DB API
        data = {
            'changeid': model.changeid,
            'author': model.author,
            'committer': model.committer,
            'comments': model.comments,
            'branch': model.branch,
            'revision': model.revision,
            'revlink': model.revlink,
            'when_timestamp': datetime2epoch(model.when_timestamp),
            'category': model.category,
            'parent_changeids': model.parent_changeids,
            'repository': model.repository,
            'codebase': model.codebase,
            'project': model.project,
            'files': model.files,
        }

        sskey = ('sourcestamps', str(model.sourcestampid))
        assert hasattr(self, "master"), "FixerMixin requires a master attribute"
        data['sourcestamp'] = yield self.master.data.get(sskey)
        data['properties'] = model.properties

        return data

    fieldMapping = {
        'author': 'changes.author',
        'branch': 'changes.branch',
        'category': 'changes.category',
        'changeid': 'changes.changeid',
        'codebase': 'changes.codebase',
        'comments': 'changes.comments',
        'committer': 'changes.committer',
        'project': 'changes.project',
        'repository': 'changes.repository',
        'revision': 'changes.revision',
        'revlink': 'changes.revlink',
        'sourcestampid': 'changes.sourcestampid',
        'when_timestamp': 'changes.when_timestamp',
    }


class ChangeEndpoint(FixerMixin, base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/changes/n:changeid",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        change = yield self.master.db.changes.getChange(kwargs['changeid'])
        if change is None:
            return None
        return (yield self._fixChange(change))


class ChangesEndpoint(FixerMixin, base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/changes",
        "/builders/n:builderid/builds/n:build_number/changes",
        "/builds/n:buildid/changes",
        "/sourcestamps/n:ssid/changes",
    ]
    rootLinkName = 'changes'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        buildid = kwargs.get('buildid')
        if 'build_number' in kwargs:
            buildid = yield self.getBuildid(kwargs)
        ssid = kwargs.get('ssid')
        changes = []
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
            results.append((yield self._fixChange(ch)))
        return results


class Change(base.ResourceType):
    name = "change"
    plural = "changes"
    endpoints = [ChangeEndpoint, ChangesEndpoint]
    eventPathPatterns = [
        "/changes/:changeid",
    ]

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

    entityType = EntityType(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def addChange(
        self,
        files: list[str] | None = None,
        comments: str | None = None,
        author: str | None = None,
        committer: str | None = None,
        revision: str | None = None,
        when_timestamp: int | None = None,
        branch: str | None = None,
        category: str | Callable | None = None,
        revlink: str | None = '',
        properties: dict[str, Any] | None = None,
        repository: str = '',
        codebase: str | None = None,
        project: str = '',
        src: str | None = None,
        _test_changeid: int | None = None,
    ):
        metrics.MetricCountEvent.log("added_changes", 1)

        if properties is None:
            properties = {}
        # add the source to the properties
        for k in properties:
            properties[k] = (properties[k], 'Change')

        # get a user id
        if src:
            # create user object, returning a corresponding uid
            uid = yield users.createUserObject(self.master, author, src)
        else:
            uid = None

        if not revlink and revision and repository and callable(self.master.config.revlink):
            # generate revlink from revision and repository using the configured callable
            revlink = self.master.config.revlink(revision, repository) or ''

        if callable(category):
            pre_change = self.master.config.preChangeGenerator(
                author=author,
                committer=committer,
                files=files,
                comments=comments,
                revision=revision,
                when_timestamp=when_timestamp,
                branch=branch,
                revlink=revlink,
                properties=properties,
                repository=repository,
                project=project,
            )
            category = category(pre_change)

        # set the codebase, either the default, supplied, or generated
        if codebase is None and self.master.config.codebaseGenerator is not None:
            pre_change = self.master.config.preChangeGenerator(
                author=author,
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
                project=project,
            )
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
            uid=uid,
            _test_changeid=_test_changeid,
        )

        # get the change and munge the result for the notification
        change = yield self.master.data.get(('changes', str(changeid)))
        change = copy.deepcopy(change)
        self.produceEvent(change, 'new')

        # log, being careful to handle funny characters
        msg = f"added change with revision {revision} to database"
        log.msg(msg.encode('utf-8', 'replace'))

        return changeid

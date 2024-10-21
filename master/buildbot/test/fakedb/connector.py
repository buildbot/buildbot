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

import json

from twisted.internet import defer

from buildbot.db.connector import DBConnector
from buildbot.util.sautils import hash_columns

from .build_data import BuildData
from .builders import Builder
from .builders import BuilderMaster
from .builders import BuildersTags
from .buildrequests import BuildRequest
from .buildrequests import BuildRequestClaim
from .builds import Build
from .builds import BuildProperty
from .buildsets import Buildset
from .buildsets import BuildsetProperty
from .buildsets import BuildsetSourceStamp
from .changes import Change
from .changes import ChangeFile
from .changes import ChangeProperty
from .changes import ChangeUser
from .changesources import ChangeSource
from .changesources import ChangeSourceMaster
from .logs import Log
from .logs import LogChunk
from .masters import Master
from .projects import Project
from .schedulers import Scheduler
from .schedulers import SchedulerChange
from .schedulers import SchedulerMaster
from .sourcestamps import Patch
from .sourcestamps import SourceStamp
from .state import Object
from .state import ObjectState
from .steps import Step
from .tags import Tag
from .test_result_sets import TestResultSet
from .test_results import TestCodePath
from .test_results import TestName
from .test_results import TestResult
from .users import User
from .users import UserInfo
from .workers import ConfiguredWorker
from .workers import ConnectedWorker
from .workers import Worker


class FakeDBConnector(DBConnector):
    """
    A stand-in for C{master.db} that operates without an actual database
    backend.  This also implements a test-data interface similar to the
    L{buildbot.test.util.db.RealDatabaseMixin.insert_test_data} method.

    The child classes implement various useful assertions and faking methods;
    see their documentation for more.
    """

    MASTER_ID = 824

    def __init__(self, basedir, testcase, auto_upgrade=False):
        super().__init__(basedir)
        self.testcase = testcase
        self.checkForeignKeys = False
        self.auto_upgrade = auto_upgrade

    @defer.inlineCallbacks
    def setup(self):
        if self.auto_upgrade:
            yield super().setup(check_version=False)
            yield self.model.upgrade()
        else:
            yield super().setup()

    def _match_rows(self, rows, type):
        matched_rows = [r for r in rows if isinstance(r, type)]
        non_matched_rows = [r for r in rows if r not in matched_rows]
        return matched_rows, non_matched_rows

    def _thd_maybe_insert_build_data(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, BuildData)
        for row in matched_rows:
            conn.execute(
                self.model.build_data.insert(),
                [
                    {
                        'id': row.id,
                        'buildid': row.buildid,
                        'name': row.name,
                        'value': row.value,
                        'length': row.length,
                        'source': row.source,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_builder(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, Builder)
        for row in matched_rows:
            conn.execute(
                self.model.builders.insert(),
                [
                    {
                        'id': row.id,
                        'name': row.name,
                        'name_hash': hash_columns(row.name),
                        'projectid': row.projectid,
                        'description': row.description,
                        'description_format': row.description_format,
                        'description_html': row.description_html,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_builder_master(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, BuilderMaster)
        for row in matched_rows:
            conn.execute(
                self.model.builder_masters.insert(),
                [{'id': row.id, 'builderid': row.builderid, 'masterid': row.masterid}],
            )
        return non_matched_rows

    def _thd_maybe_insert_builder_tags(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, BuildersTags)
        for row in matched_rows:
            conn.execute(
                self.model.builders_tags.insert(),
                [{'builderid': row.builderid, 'tagid': row.tagid}],
            )
        return non_matched_rows

    def _thd_maybe_insert_buildrequest(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, BuildRequest)
        for row in matched_rows:
            conn.execute(
                self.model.buildrequests.insert(),
                [
                    {
                        'id': row.id,
                        'buildsetid': row.buildsetid,
                        'builderid': row.builderid,
                        'priority': row.priority,
                        'complete': row.complete,
                        'results': row.results,
                        'submitted_at': row.submitted_at,
                        'complete_at': row.complete_at,
                        'waited_for': row.waited_for,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_buildrequest_claim(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, BuildRequestClaim)
        for row in matched_rows:
            conn.execute(
                self.model.buildrequest_claims.insert(),
                [
                    {
                        'brid': row.brid,
                        'masterid': row.masterid,
                        'claimed_at': row.claimed_at,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_build(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, Build)
        for row in matched_rows:
            conn.execute(
                self.model.builds.insert(),
                [
                    {
                        'id': row.id,
                        'number': row.number,
                        'builderid': row.builderid,
                        'buildrequestid': row.buildrequestid,
                        'workerid': row.workerid,
                        'masterid': row.masterid,
                        'started_at': row.started_at,
                        'complete_at': row.complete_at,
                        'locks_duration_s': row.locks_duration_s,
                        'state_string': row.state_string,
                        'results': row.results,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_build_properties(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, BuildProperty)
        for row in matched_rows:
            conn.execute(
                self.model.build_properties.insert(),
                [
                    {
                        'buildid': row.buildid,
                        'name': row.name,
                        'value': json.dumps(row.value),
                        'source': row.source,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_buildset(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, Buildset)
        for row in matched_rows:
            conn.execute(
                self.model.buildsets.insert(),
                [
                    {
                        'id': row.id,
                        'external_idstring': row.external_idstring,
                        'reason': row.reason,
                        'submitted_at': row.submitted_at,
                        'complete': row.complete,
                        'complete_at': row.complete_at,
                        'results': row.results,
                        'parent_buildid': row.parent_buildid,
                        'parent_relationship': row.parent_relationship,
                        'rebuilt_buildid': row.rebuilt_buildid,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_buildset_property(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, BuildsetProperty)
        for row in matched_rows:
            conn.execute(
                self.model.buildset_properties.insert(),
                [
                    {
                        'buildsetid': row.buildsetid,
                        'property_name': row.property_name,
                        'property_value': row.property_value,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_buildset_sourcestamp(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, BuildsetSourceStamp)
        for row in matched_rows:
            conn.execute(
                self.model.buildset_sourcestamps.insert(),
                [
                    {
                        'id': row.id,
                        'buildsetid': row.buildsetid,
                        'sourcestampid': row.sourcestampid,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_change(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, Change)
        for row in matched_rows:
            conn.execute(
                self.model.changes.insert(),
                [
                    {
                        'changeid': row.changeid,
                        'author': row.author,
                        'committer': row.committer,
                        'comments': row.comments,
                        'branch': row.branch,
                        'revision': row.revision,
                        'revlink': row.revlink,
                        'when_timestamp': row.when_timestamp,
                        'category': row.category,
                        'repository': row.repository,
                        'codebase': row.codebase,
                        'project': row.project,
                        'sourcestampid': row.sourcestampid,
                        'parent_changeids': row.parent_changeids,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_change_file(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, ChangeFile)
        for row in matched_rows:
            conn.execute(
                self.model.change_files.insert(),
                [{'changeid': row.changeid, 'filename': row.filename}],
            )
        return non_matched_rows

    def _thd_maybe_insert_change_property(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, ChangeProperty)
        for row in matched_rows:
            conn.execute(
                self.model.change_properties.insert(),
                [
                    {
                        'changeid': row.changeid,
                        'property_name': row.property_name,
                        'property_value': row.property_value,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_change_user(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, ChangeUser)
        for row in matched_rows:
            conn.execute(
                self.model.change_users.insert(),
                [{'changeid': row.changeid, 'uid': row.uid}],
            )
        return non_matched_rows

    def _thd_maybe_insert_changesource(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, ChangeSource)
        for row in matched_rows:
            conn.execute(
                self.model.changesources.insert(),
                [
                    {
                        'id': row.id,
                        'name': row.name,
                        'name_hash': hash_columns(row.name),
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_changesource_master(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, ChangeSourceMaster)
        for row in matched_rows:
            conn.execute(
                self.model.changesource_masters.insert(),
                [
                    {
                        'changesourceid': row.changesourceid,
                        'masterid': row.masterid,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_log(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, Log)
        for row in matched_rows:
            conn.execute(
                self.model.logs.insert(),
                [
                    {
                        'id': row.id,
                        'name': row.name,
                        'slug': row.slug,
                        'stepid': row.stepid,
                        'complete': row.complete,
                        'num_lines': row.num_lines,
                        'type': row.type,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_log_chunk(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, LogChunk)
        for row in matched_rows:
            conn.execute(
                self.model.logchunks.insert(),
                [
                    {
                        'logid': row.logid,
                        'first_line': row.first_line,
                        'last_line': row.last_line,
                        'content': row.content,
                        'compressed': row.compressed,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_master(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, Master)
        for row in matched_rows:
            conn.execute(
                self.model.masters.insert(),
                [
                    {
                        'id': row.id,
                        'name': row.name,
                        'name_hash': hash_columns(row.name),
                        'active': row.active,
                        'last_active': row.last_active,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_project(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, Project)
        for row in matched_rows:
            conn.execute(
                self.model.projects.insert(),
                [
                    {
                        'id': row.id,
                        'name': row.name,
                        'name_hash': hash_columns(row.name),
                        'slug': row.slug,
                        'description': row.description,
                        'description_format': row.description_format,
                        'description_html': row.description_html,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_scheduler_change(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, SchedulerChange)
        for row in matched_rows:
            conn.execute(
                self.model.scheduler_changes.insert(),
                [
                    {
                        'schedulerid': row.schedulerid,
                        'changeid': row.changeid,
                        'important': row.important,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_scheduler(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, Scheduler)
        for row in matched_rows:
            conn.execute(
                self.model.schedulers.insert(),
                [
                    {
                        'id': row.id,
                        'name': row.name,
                        'name_hash': hash_columns(row.name),
                        'enabled': row.enabled,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_scheduler_master(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, SchedulerMaster)
        for row in matched_rows:
            conn.execute(
                self.model.scheduler_masters.insert(),
                [
                    {
                        'schedulerid': row.schedulerid,
                        'masterid': row.masterid,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_patch(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, Patch)
        for row in matched_rows:
            conn.execute(
                self.model.patches.insert(),
                [
                    {
                        'id': row.id,
                        'patchlevel': row.patchlevel,
                        'patch_base64': row.patch_base64,
                        'patch_author': row.patch_author,
                        'patch_comment': row.patch_comment,
                        'subdir': row.subdir,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_sourcestamp(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, SourceStamp)
        for row in matched_rows:
            conn.execute(
                self.model.sourcestamps.insert(),
                [
                    {
                        'id': row.id,
                        'branch': row.branch,
                        'revision': row.revision,
                        'patchid': row.patchid,
                        'repository': row.repository,
                        'codebase': row.codebase,
                        'project': row.project,
                        'created_at': row.created_at,
                        'ss_hash': hash_columns(
                            row.branch,
                            row.revision,
                            row.repository,
                            row.project,
                            row.codebase,
                            row.patchid,
                        ),
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_object(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, Object)
        for row in matched_rows:
            conn.execute(
                self.model.objects.insert(),
                [
                    {
                        'id': row.id,
                        'name': row.name,
                        'class_name': row.class_name,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_object_state(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, ObjectState)
        for row in matched_rows:
            conn.execute(
                self.model.object_state.insert(),
                [
                    {
                        'objectid': row.objectid,
                        'name': row.name,
                        'value_json': row.value_json,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_step(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, Step)
        for row in matched_rows:
            conn.execute(
                self.model.steps.insert(),
                [
                    {
                        'id': row.id,
                        'number': row.number,
                        'name': row.name,
                        'buildid': row.buildid,
                        'started_at': row.started_at,
                        'locks_acquired_at': row.locks_acquired_at,
                        'complete_at': row.complete_at,
                        'state_string': row.state_string,
                        'results': row.results,
                        'urls_json': row.urls_json,
                        'hidden': row.hidden,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_tag(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, Tag)
        for row in matched_rows:
            conn.execute(
                self.model.tags.insert(),
                [
                    {
                        'id': row.id,
                        'name': row.name,
                        'name_hash': hash_columns(row.name),
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_test_result_set(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, TestResultSet)
        for row in matched_rows:
            conn.execute(
                self.model.test_result_sets.insert(),
                [
                    {
                        'id': row.id,
                        'builderid': row.builderid,
                        'buildid': row.buildid,
                        'stepid': row.stepid,
                        'description': row.description,
                        'category': row.category,
                        'value_unit': row.value_unit,
                        'tests_passed': row.tests_passed,
                        'tests_failed': row.tests_failed,
                        'complete': row.complete,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_test_name(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, TestName)
        for row in matched_rows:
            conn.execute(
                self.model.test_names.insert(),
                [
                    {
                        'id': row.id,
                        'builderid': row.builderid,
                        'name': row.name,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_test_code_path(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, TestCodePath)
        for row in matched_rows:
            conn.execute(
                self.model.test_code_paths.insert(),
                [
                    {
                        'id': row.id,
                        'builderid': row.builderid,
                        'path': row.path,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_test_result(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, TestResult)
        for row in matched_rows:
            conn.execute(
                self.model.test_results.insert(),
                [
                    {
                        'id': row.id,
                        'builderid': row.builderid,
                        'test_result_setid': row.test_result_setid,
                        'test_nameid': row.test_nameid,
                        'test_code_pathid': row.test_code_pathid,
                        'line': row.line,
                        'duration_ns': row.duration_ns,
                        'value': row.value,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_user(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, User)
        for row in matched_rows:
            conn.execute(
                self.model.users.insert(),
                [
                    {
                        'uid': row.uid,
                        'identifier': row.identifier,
                        'bb_username': row.bb_username,
                        'bb_password': row.bb_password,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_user_info(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, UserInfo)
        for row in matched_rows:
            conn.execute(
                self.model.users_info.insert(),
                [
                    {
                        'uid': row.uid,
                        'attr_type': row.attr_type,
                        'attr_data': row.attr_data,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_worker(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, Worker)
        for row in matched_rows:
            conn.execute(
                self.model.workers.insert(),
                [
                    {
                        'id': row.id,
                        'name': row.name,
                        'info': row.info,
                        'paused': row.paused,
                        'pause_reason': row.pause_reason,
                        'graceful': row.graceful,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_configured_worker(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, ConfiguredWorker)
        for row in matched_rows:
            conn.execute(
                self.model.configured_workers.insert(),
                [
                    {
                        'id': row.id,
                        'buildermasterid': row.buildermasterid,
                        'workerid': row.workerid,
                    }
                ],
            )
        return non_matched_rows

    def _thd_maybe_insert_connected_worker(self, conn, rows):
        matched_rows, non_matched_rows = self._match_rows(rows, ConnectedWorker)
        for row in matched_rows:
            conn.execute(
                self.model.connected_workers.insert(),
                [{'id': row.id, 'masterid': row.masterid, 'workerid': row.workerid}],
            )
        return non_matched_rows

    @defer.inlineCallbacks
    def insert_test_data(self, rows):
        """Insert a list of Row instances into the database"""

        def thd_insert_rows(conn):
            remaining = rows
            remaining = self._thd_maybe_insert_build_data(conn, remaining)
            remaining = self._thd_maybe_insert_builder(conn, remaining)
            remaining = self._thd_maybe_insert_builder_master(conn, remaining)
            remaining = self._thd_maybe_insert_builder_tags(conn, remaining)
            remaining = self._thd_maybe_insert_buildrequest(conn, remaining)
            remaining = self._thd_maybe_insert_buildrequest_claim(conn, remaining)
            remaining = self._thd_maybe_insert_build(conn, remaining)
            remaining = self._thd_maybe_insert_build_properties(conn, remaining)
            remaining = self._thd_maybe_insert_buildset(conn, remaining)
            remaining = self._thd_maybe_insert_buildset_property(conn, remaining)
            remaining = self._thd_maybe_insert_buildset_sourcestamp(conn, remaining)
            remaining = self._thd_maybe_insert_change(conn, remaining)
            remaining = self._thd_maybe_insert_change_file(conn, remaining)
            remaining = self._thd_maybe_insert_change_property(conn, remaining)
            remaining = self._thd_maybe_insert_change_user(conn, remaining)
            remaining = self._thd_maybe_insert_changesource(conn, remaining)
            remaining = self._thd_maybe_insert_changesource_master(conn, remaining)
            remaining = self._thd_maybe_insert_log(conn, remaining)
            remaining = self._thd_maybe_insert_log_chunk(conn, remaining)
            remaining = self._thd_maybe_insert_master(conn, remaining)
            remaining = self._thd_maybe_insert_project(conn, remaining)
            remaining = self._thd_maybe_insert_scheduler_change(conn, remaining)
            remaining = self._thd_maybe_insert_scheduler(conn, remaining)
            remaining = self._thd_maybe_insert_scheduler_master(conn, remaining)
            remaining = self._thd_maybe_insert_patch(conn, remaining)
            remaining = self._thd_maybe_insert_sourcestamp(conn, remaining)
            remaining = self._thd_maybe_insert_object(conn, remaining)
            remaining = self._thd_maybe_insert_object_state(conn, remaining)
            remaining = self._thd_maybe_insert_step(conn, remaining)
            remaining = self._thd_maybe_insert_tag(conn, remaining)
            remaining = self._thd_maybe_insert_test_result_set(conn, remaining)
            remaining = self._thd_maybe_insert_test_name(conn, remaining)
            remaining = self._thd_maybe_insert_test_code_path(conn, remaining)
            remaining = self._thd_maybe_insert_test_result(conn, remaining)
            remaining = self._thd_maybe_insert_user(conn, remaining)
            remaining = self._thd_maybe_insert_user_info(conn, remaining)
            remaining = self._thd_maybe_insert_worker(conn, remaining)
            remaining = self._thd_maybe_insert_configured_worker(conn, remaining)
            remaining = self._thd_maybe_insert_connected_worker(conn, remaining)

            self.testcase.assertEqual(remaining, [])

            conn.commit()

            for row in rows:
                if self.checkForeignKeys:
                    row.checkForeignKeys(self, self.testcase)

        yield self.pool.do(thd_insert_rows)

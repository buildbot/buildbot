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


import alembic
import alembic.config
import sqlalchemy as sa

from twisted.internet import defer
from twisted.python import log
from twisted.python import util

from buildbot.db import base
from buildbot.db.migrate_utils import test_unicode
from buildbot.db.types.json import JsonObject
from buildbot.util import sautils


class UpgradeFromBefore0p9Error(Exception):

    def __init__(self):
        message = """You are trying to upgrade a buildbot 0.8.x master to buildbot 0.9.x or newer.
        This is not supported. Please start from a clean database
        http://docs.buildbot.net/latest/manual/upgrading/0.9-upgrade.html"""
        # Call the base class constructor with the parameters it needs
        super().__init__(message)


class UpgradeFromBefore3p0Error(Exception):

    def __init__(self):
        message = """You are trying to upgrade to Buildbot 3.0 or newer from Buildbot 2.x or older.
        This is only supported via an intermediate upgrade to newest Buildbot 2.10.x that is
        available. Please first upgrade to 2.10.x and then try to upgrade to this version.
        http://docs.buildbot.net/latest/manual/upgrading/3.0-upgrade.html"""
        super().__init__(message)


class Model(base.DBConnectorComponent):

    property_name_length = 256
    property_source_length = 256
    hash_length = 40

    #
    # schema
    #

    metadata = sa.MetaData()

    # NOTES

    # * server_defaults here are included to match those added by the migration
    #   scripts, but they should not be depended on - all code accessing these
    #   tables should supply default values as necessary.  The defaults are
    #   required during migration when adding non-nullable columns to existing
    #   tables.
    #
    # * dates are stored as unix timestamps (UTC-ish epoch time)
    #
    # * sqlalchemy does not handle sa.Boolean very well on MySQL or Postgres;
    #   use sa.SmallInteger instead
    #
    # * BuildRequest.canBeCollapsed() depends on buildrequest.id being auto-incremented which is
    #   sqlalchemy default.

    # Tables related to build requests
    # --------------------------------

    # A BuildRequest is a request for a particular build to be performed.  Each
    # BuildRequest is a part of a Buildset.  BuildRequests are claimed by
    # masters, to avoid multiple masters running the same build.
    buildrequests = sautils.Table(
        'buildrequests', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('buildsetid', sa.Integer,
                  sa.ForeignKey('buildsets.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('builderid', sa.Integer,
                  sa.ForeignKey('builders.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('priority', sa.Integer, nullable=False,
                  server_default=sa.DefaultClause("0")),

        # if this is zero, then the build is still pending
        sa.Column('complete', sa.Integer,
                  server_default=sa.DefaultClause("0")),

        # results is only valid when complete == 1; 0 = SUCCESS, 1 = WARNINGS,
        # etc - see master/buildbot/status/builder.py
        sa.Column('results', sa.SmallInteger),

        # time the buildrequest was created
        sa.Column('submitted_at', sa.Integer, nullable=False),

        # time the buildrequest was completed, or NULL
        sa.Column('complete_at', sa.Integer),

        # boolean indicating whether there is a step blocking, waiting for this
        # request to complete
        sa.Column('waited_for', sa.SmallInteger,
                  server_default=sa.DefaultClause("0")),
    )

    # Each row in this table represents a claimed build request, where the
    # claim is made by the master referenced by masterid.
    buildrequest_claims = sautils.Table(
        'buildrequest_claims', metadata,
        sa.Column('brid', sa.Integer,
                  sa.ForeignKey('buildrequests.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('masterid', sa.Integer,
                  sa.ForeignKey('masters.id', ondelete='CASCADE'),
                  index=True, nullable=False),
        sa.Column('claimed_at', sa.Integer, nullable=False),
    )

    # Tables related to builds
    # ------------------------

    # This table contains the build properties
    build_properties = sautils.Table(
        'build_properties', metadata,
        sa.Column('buildid', sa.Integer,
                  sa.ForeignKey('builds.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('name', sa.String(property_name_length), nullable=False),
        # JSON encoded value
        sa.Column('value', sa.Text, nullable=False),
        sa.Column('source', sa.String(property_source_length), nullable=False),
    )

    # This table contains transient build state.
    build_data = sautils.Table(
        'build_data', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('buildid', sa.Integer,
                  sa.ForeignKey('builds.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('name', sa.String(256), nullable=False),
        sa.Column('value', sa.LargeBinary().with_variant(sa.dialects.mysql.LONGBLOB, "mysql"),
                  nullable=False),
        sa.Column('length', sa.Integer, nullable=False),
        sa.Column('source', sa.String(256), nullable=False),
    )

    # This table contains basic information about each build.
    builds = sautils.Table(
        'builds', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('number', sa.Integer, nullable=False),
        sa.Column('builderid', sa.Integer,
                  sa.ForeignKey('builders.id', ondelete='CASCADE'),
                  nullable=False),
        # note that there is 1:N relationship here.
        # In case of worker loss, build has results RETRY
        # and buildrequest is unclaimed.
        # We use use_alter to prevent circular reference
        # (buildrequests -> buildsets -> builds).
        sa.Column('buildrequestid', sa.Integer,
                  sa.ForeignKey(
                      'buildrequests.id', use_alter=True,
                      name='buildrequestid', ondelete='CASCADE'),
                  nullable=False),
        # worker which performed this build
        # keep nullable to support worker-free builds
        sa.Column('workerid', sa.Integer,
                  sa.ForeignKey('workers.id', ondelete='SET NULL'),
                  nullable=True),
        # master which controlled this build
        sa.Column('masterid', sa.Integer,
                  sa.ForeignKey('masters.id', ondelete='CASCADE'),
                  nullable=False),
        # start/complete times
        sa.Column('started_at', sa.Integer, nullable=False),
        sa.Column('complete_at', sa.Integer),
        sa.Column('state_string', sa.Text, nullable=False),
        sa.Column('results', sa.Integer),
    )

    # Tables related to steps
    # -----------------------

    steps = sautils.Table(
        'steps', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('number', sa.Integer, nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('buildid', sa.Integer,
                  sa.ForeignKey('builds.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('started_at', sa.Integer),
        sa.Column('complete_at', sa.Integer),
        sa.Column('state_string', sa.Text, nullable=False),
        sa.Column('results', sa.Integer),
        sa.Column('urls_json', sa.Text, nullable=False),
        sa.Column(
            'hidden', sa.SmallInteger, nullable=False, server_default='0'),
    )

    # Tables related to logs
    # ----------------------

    logs = sautils.Table(
        'logs', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('slug', sa.String(50), nullable=False),
        sa.Column('stepid', sa.Integer,
                  sa.ForeignKey('steps.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('complete', sa.SmallInteger, nullable=False),
        sa.Column('num_lines', sa.Integer, nullable=False),
        # 's' = stdio, 't' = text, 'h' = html, 'd' = deleted
        sa.Column('type', sa.String(1), nullable=False),
    )

    logchunks = sautils.Table(
        'logchunks', metadata,
        sa.Column('logid', sa.Integer,
                  sa.ForeignKey('logs.id', ondelete='CASCADE'),
                  nullable=False),
        # 0-based line number range in this chunk (inclusive); note that for
        # HTML logs, this counts lines of HTML, not lines of rendered output
        sa.Column('first_line', sa.Integer, nullable=False),
        sa.Column('last_line', sa.Integer, nullable=False),
        # log contents, including a terminating newline, encoded in utf-8 or,
        # if 'compressed' is not 0, compressed with gzip, bzip2 or lz4
        sa.Column('content', sa.LargeBinary(65536)),
        sa.Column('compressed', sa.SmallInteger, nullable=False),
    )

    # Tables related to buildsets
    # ---------------------------

    # This table contains input properties for buildsets
    buildset_properties = sautils.Table(
        'buildset_properties', metadata,
        sa.Column('buildsetid', sa.Integer,
                  sa.ForeignKey('buildsets.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('property_name', sa.String(property_name_length), nullable=False),
        # JSON-encoded tuple of (value, source)
        sa.Column('property_value', sa.Text, nullable=False),
    )

    # This table represents Buildsets - sets of BuildRequests that share the
    # same original cause and source information.
    buildsets = sautils.Table(
        'buildsets', metadata,
        sa.Column('id', sa.Integer, primary_key=True),

        # a simple external identifier to track down this buildset later, e.g.,
        # for try requests
        sa.Column('external_idstring', sa.String(256)),

        # a short string giving the reason the buildset was created
        sa.Column('reason', sa.String(256)),
        sa.Column('submitted_at', sa.Integer, nullable=False),

        # if this is zero, then the build set is still pending
        sa.Column('complete', sa.SmallInteger, nullable=False,
                  server_default=sa.DefaultClause("0")),
        sa.Column('complete_at', sa.Integer),

        # results is only valid when complete == 1; 0 = SUCCESS, 1 = WARNINGS,
        # etc - see master/buildbot/status/builder.py
        sa.Column('results', sa.SmallInteger),

        # optional parent build, we use use_alter to prevent circular reference
        # http://docs.sqlalchemy.org/en/latest/orm/relationships.html#rows-that-point-to-themselves-mutually-dependent-rows
        sa.Column('parent_buildid', sa.Integer,
                  sa.ForeignKey('builds.id', use_alter=True,
                                name='parent_buildid', ondelete='SET NULL'),
                  nullable=True),
        # text describing what is the relationship with the build
        # could be 'triggered from', 'rebuilt from', 'inherited from'
        sa.Column('parent_relationship', sa.Text),
    )

    # Tables related to change sources
    # --------------------------------

    # The changesources table gives a unique identifier to each ChangeSource.  It
    # also links to other tables used to ensure only one master runs each
    # changesource
    changesources = sautils.Table(
        'changesources', metadata,
        sa.Column("id", sa.Integer, primary_key=True),

        # name for this changesource, as given in the configuration, plus a hash
        # of that name used for a unique index
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('name_hash', sa.String(hash_length), nullable=False),
    )

    # This links changesources to the master where they are running.  A changesource
    # linked to a master that is inactive can be unlinked by any master.  This
    # is a separate table so that we can "claim" changesources on a master by
    # inserting; this has better support in database servers for ensuring that
    # exactly one claim succeeds.
    changesource_masters = sautils.Table(
        'changesource_masters', metadata,
        sa.Column('changesourceid', sa.Integer,
                  sa.ForeignKey('changesources.id', ondelete='CASCADE'),
                  nullable=False, primary_key=True),
        sa.Column('masterid', sa.Integer,
                  sa.ForeignKey('masters.id', ondelete='CASCADE'),
                  nullable=False),
    )

    # Tables related to workers
    # -------------------------

    workers = sautils.Table(
        "workers", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("info", JsonObject, nullable=False),
        sa.Column("paused", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("graceful", sa.SmallInteger, nullable=False, server_default="0"),
    )

    # link workers to all builder/master pairs for which they are
    # configured
    configured_workers = sautils.Table(
        'configured_workers', metadata,
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('buildermasterid', sa.Integer,
                  sa.ForeignKey('builder_masters.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('workerid', sa.Integer,
                  sa.ForeignKey('workers.id', ondelete='CASCADE'),
                  nullable=False),
    )

    # link workers to the masters they are currently connected to
    connected_workers = sautils.Table(
        'connected_workers', metadata,
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('masterid', sa.Integer,
                  sa.ForeignKey('masters.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('workerid', sa.Integer,
                  sa.ForeignKey('workers.id', ondelete='CASCADE'),
                  nullable=False),
    )

    # Tables related to changes
    # ----------------------------

    # Files touched in changes
    change_files = sautils.Table(
        'change_files', metadata,
        sa.Column('changeid', sa.Integer,
                  sa.ForeignKey('changes.changeid', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('filename', sa.String(1024), nullable=False),
    )

    # Properties for changes
    change_properties = sautils.Table(
        'change_properties', metadata,
        sa.Column('changeid', sa.Integer,
                  sa.ForeignKey('changes.changeid', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('property_name', sa.String(property_name_length), nullable=False),
        # JSON-encoded tuple of (value, source)
        sa.Column('property_value', sa.Text, nullable=False),
    )

    # users associated with this change; this allows multiple users for
    # situations where a version-control system can represent both an author
    # and committer, for example.
    change_users = sautils.Table(
        "change_users", metadata,
        sa.Column('changeid', sa.Integer,
                  sa.ForeignKey('changes.changeid', ondelete='CASCADE'),
                  nullable=False),
        # uid for the author of the change with the given changeid
        sa.Column('uid', sa.Integer,
                  sa.ForeignKey('users.uid', ondelete='CASCADE'),
                  nullable=False),
    )

    # Changes to the source code, produced by ChangeSources
    changes = sautils.Table(
        'changes', metadata,
        # changeid also serves as 'change number'
        sa.Column('changeid', sa.Integer, primary_key=True),

        # author's name (usually an email address)
        sa.Column('author', sa.String(255), nullable=False),

        # committer's name
        sa.Column('committer', sa.String(255), nullable=True),

        # commit comment
        sa.Column('comments', sa.Text, nullable=False),

        # The branch where this change occurred.  When branch is NULL, that
        # means the main branch (trunk, master, etc.)
        sa.Column('branch', sa.String(255)),

        # revision identifier for this change
        sa.Column('revision', sa.String(255)),  # CVS uses NULL

        sa.Column('revlink', sa.String(256)),

        # this is the timestamp of the change - it is usually copied from the
        # version-control system, and may be long in the past or even in the
        # future!
        sa.Column('when_timestamp', sa.Integer, nullable=False),

        # an arbitrary string used for filtering changes
        sa.Column('category', sa.String(255)),

        # repository specifies, along with revision and branch, the
        # source tree in which this change was detected.
        sa.Column('repository', sa.String(length=512), nullable=False,
                  server_default=''),

        # codebase is a logical name to specify what is in the repository
        sa.Column('codebase', sa.String(256), nullable=False,
                  server_default=sa.DefaultClause("")),

        # project names the project this source code represents.  It is used
        # later to filter changes
        sa.Column('project', sa.String(length=512), nullable=False,
                  server_default=''),

        # the sourcestamp this change brought the codebase to
        sa.Column('sourcestampid', sa.Integer,
                  sa.ForeignKey('sourcestamps.id', ondelete='CASCADE'),
                  nullable=False),

        # The parent of the change
        # Even if for the moment there's only 1 parent for a change, we use plural here because
        # somedays a change will have multiple parent. This way we don't need
        # to change the API
        sa.Column('parent_changeids', sa.Integer,
                  sa.ForeignKey('changes.changeid', ondelete='SET NULL'),
                  nullable=True),
    )

    # Tables related to sourcestamps
    # ------------------------------

    # Patches for SourceStamps that were generated through the try mechanism
    patches = sautils.Table(
        'patches', metadata,
        sa.Column('id', sa.Integer, primary_key=True),

        # number of directory levels to strip off (patch -pN)
        sa.Column('patchlevel', sa.Integer, nullable=False),

        # base64-encoded version of the patch file
        sa.Column('patch_base64', sa.Text, nullable=False),

        # patch author, if known
        sa.Column('patch_author', sa.Text, nullable=False),

        # patch comment
        sa.Column('patch_comment', sa.Text, nullable=False),

        # subdirectory in which the patch should be applied; NULL for top-level
        sa.Column('subdir', sa.Text),
    )

    # A sourcestamp identifies a particular instance of the source code.
    # Ideally, this would always be absolute, but in practice source stamps can
    # also mean "latest" (when revision is NULL), which is of course a
    # time-dependent definition.
    sourcestamps = sautils.Table(
        'sourcestamps', metadata,
        sa.Column('id', sa.Integer, primary_key=True),

        # hash of the branch, revision, patchid, repository, codebase, and
        # project, using hashColumns.
        sa.Column('ss_hash', sa.String(hash_length), nullable=False),

        # the branch to check out.  When branch is NULL, that means
        # the main branch (trunk, master, etc.)
        sa.Column('branch', sa.String(256)),

        # the revision to check out, or the latest if NULL
        sa.Column('revision', sa.String(256)),

        # the patch to apply to generate this source code
        sa.Column('patchid', sa.Integer,
                  sa.ForeignKey('patches.id', ondelete='CASCADE'),
                  nullable=True),

        # the repository from which this source should be checked out
        sa.Column('repository', sa.String(length=512), nullable=False,
                  server_default=''),

        # codebase is a logical name to specify what is in the repository
        sa.Column('codebase', sa.String(256), nullable=False,
                  server_default=sa.DefaultClause("")),

        # the project this source code represents
        sa.Column('project', sa.String(length=512), nullable=False,
                  server_default=''),

        # the time this sourcetamp was first seen (the first time it was added)
        sa.Column('created_at', sa.Integer, nullable=False),
    )

    # a many-to-may relationship between buildsets and sourcestamps
    buildset_sourcestamps = sautils.Table(
        'buildset_sourcestamps', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('buildsetid', sa.Integer,
                  sa.ForeignKey('buildsets.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('sourcestampid', sa.Integer,
                  sa.ForeignKey('sourcestamps.id', ondelete='CASCADE'),
                  nullable=False),
    )

    # Tables related to schedulers
    # ----------------------------

    # The schedulers table gives a unique identifier to each scheduler.  It
    # also links to other tables used to ensure only one master runs each
    # scheduler, and to track changes that a scheduler may trigger a build for
    # later.
    schedulers = sautils.Table(
        'schedulers', metadata,
        sa.Column("id", sa.Integer, primary_key=True),

        # name for this scheduler, as given in the configuration, plus a hash
        # of that name used for a unique index
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('name_hash', sa.String(hash_length), nullable=False),
        sa.Column('enabled', sa.SmallInteger,
                  server_default=sa.DefaultClause("1")),
    )

    # This links schedulers to the master where they are running.  A scheduler
    # linked to a master that is inactive can be unlinked by any master.  This
    # is a separate table so that we can "claim" schedulers on a master by
    # inserting; this has better support in database servers for ensuring that
    # exactly one claim succeeds.  The ID column is present for external users;
    # see bug #1053.
    scheduler_masters = sautils.Table(
        'scheduler_masters', metadata,
        sa.Column('schedulerid', sa.Integer,
                  sa.ForeignKey('schedulers.id', ondelete='CASCADE'),
                  nullable=False, primary_key=True),
        sa.Column('masterid', sa.Integer,
                  sa.ForeignKey('masters.id', ondelete='CASCADE'),
                  nullable=False),
    )

    # This table references "classified" changes that have not yet been
    # "processed".  That is, the scheduler has looked at these changes and
    # determined that something should be done, but that hasn't happened yet.
    # Rows are deleted from this table as soon as the scheduler is done with
    # the change.
    scheduler_changes = sautils.Table(
        'scheduler_changes', metadata,
        sa.Column('schedulerid', sa.Integer,
                  sa.ForeignKey('schedulers.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('changeid', sa.Integer,
                  sa.ForeignKey('changes.changeid', ondelete='CASCADE'),
                  nullable=False),
        # true (nonzero) if this change is important to this scheduler
        sa.Column('important', sa.Integer),
    )

    # Tables related to builders
    # --------------------------

    builders = sautils.Table(
        'builders', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        # builder's name
        sa.Column('name', sa.Text, nullable=False),
        # builder's description
        sa.Column('description', sa.Text, nullable=True),
        # sha1 of name; used for a unique index
        sa.Column('name_hash', sa.String(hash_length), nullable=False),
    )

    # This links builders to the master where they are running.  A builder
    # linked to a master that is inactive can be unlinked by any master.  Note
    # that builders can run on multiple masters at the same time.
    builder_masters = sautils.Table(
        'builder_masters', metadata,
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('builderid', sa.Integer,
                  sa.ForeignKey('builders.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('masterid', sa.Integer,
                  sa.ForeignKey('masters.id', ondelete='CASCADE'),
                  nullable=False),
    )

    # Tables related to tags
    # ----------------------

    tags = sautils.Table(
        'tags', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        # tag's name
        sa.Column('name', sa.Text, nullable=False),
        # sha1 of name; used for a unique index
        sa.Column('name_hash', sa.String(hash_length), nullable=False),
    )

    # a many-to-may relationship between builders and tags
    builders_tags = sautils.Table(
        'builders_tags', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('builderid', sa.Integer,
                  sa.ForeignKey('builders.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('tagid', sa.Integer,
                  sa.ForeignKey('tags.id', ondelete='CASCADE'),
                  nullable=False),
    )

    # Tables related to test results
    # ------------------------------

    # Represents a single test result set. A step can any number of test result sets,
    # each of which may contain any number of test results.
    test_result_sets = sautils.Table(
        'test_result_sets', metadata,

        sa.Column('id', sa.Integer, primary_key=True),

        # In the future we will want to rearrange the underlying data in the database according
        # to (builderid, buildid) tuple, so that huge number of entries in the table does not
        # reduce the efficiency of retrieval of data for a particular build.
        sa.Column('builderid', sa.Integer,
                  sa.ForeignKey('builders.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('buildid', sa.Integer,
                  sa.ForeignKey('builds.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('stepid', sa.Integer,
                  sa.ForeignKey('steps.id', ondelete='CASCADE'),
                  nullable=False),

        # The free-form description of the source of the test data that represent the test result
        # set.
        sa.Column('description', sa.Text, nullable=True),

        sa.Column('category', sa.Text, nullable=False),

        sa.Column('value_unit', sa.Text, nullable=False),

        # The number of passed tests in cases when the pass or fail criteria depends only on how
        # that single test runs.
        sa.Column('tests_passed', sa.Integer, nullable=True),

        # The number of failed tests in cases when the pass or fail criteria depends only on how
        # that single test runs.
        sa.Column('tests_failed', sa.Integer, nullable=True),

        # true when all test results associated with test result set have been generated.
        sa.Column('complete', sa.SmallInteger, nullable=False),
    )

    # Represents a test result. A single test result set will represent thousands of test results
    # in any significant codebase that's tested.
    #
    # A common table is used for all tests results regardless of what data they carry. Most serious
    # database engines will be able to optimize nullable fields out, so extra columns are almost
    # free when not used in such cases.
    test_results = sautils.Table(
        'test_results', metadata,

        sa.Column('id', sa.Integer, primary_key=True),

        # The builder ID of the test result set that the test result belongs to.
        # This is included for future partitioning support.
        sa.Column('builderid', sa.Integer,
                  sa.ForeignKey('builders.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('test_result_setid', sa.Integer,
                  sa.ForeignKey('test_result_sets.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('test_nameid', sa.Integer,
                  sa.ForeignKey('test_names.id', ondelete='CASCADE'),
                  nullable=True),

        sa.Column('test_code_pathid', sa.Integer,
                  sa.ForeignKey('test_code_paths.id', ondelete='CASCADE'),
                  nullable=True),

        # The code line that the test originated from
        sa.Column('line', sa.Integer, nullable=True),

        # The duration of the test execution itself
        sa.Column('duration_ns', sa.Integer, nullable=True),

        # The result of the test converted to a string.
        sa.Column('value', sa.Text, nullable=False),
    )

    # Represents the test names of test results.
    test_names = sautils.Table(
        'test_names', metadata,

        sa.Column('id', sa.Integer, primary_key=True),

        # The builder ID of the test result set that the test result belongs to.
        # This is included for future partitioning support and also for querying all test names
        # for a builder.
        sa.Column('builderid', sa.Integer,
                  sa.ForeignKey('builders.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('name', sa.Text, nullable=False),
    )

    # Represents the file paths of test results.
    test_code_paths = sautils.Table(
        'test_code_paths', metadata,

        sa.Column('id', sa.Integer, primary_key=True),

        # The builder ID of the test result set that the test result belongs to.
        # This is included for future partitioning support
        sa.Column('builderid', sa.Integer,
                  sa.ForeignKey('builders.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('path', sa.Text, nullable=False),
    )

    # Tables related to objects
    # -------------------------

    # This table uniquely identifies objects that need to maintain state across
    # invocations.
    objects = sautils.Table(
        "objects", metadata,
        # unique ID for this object
        sa.Column("id", sa.Integer, primary_key=True),
        # object's user-given name
        sa.Column('name', sa.String(128), nullable=False),
        # object's class name, basically representing a "type" for the state
        sa.Column('class_name', sa.String(128), nullable=False),
    )

    # This table stores key/value pairs for objects, where the key is a string
    # and the value is a JSON string.
    object_state = sautils.Table(
        "object_state", metadata,
        # object for which this value is set
        sa.Column('objectid', sa.Integer,
                  sa.ForeignKey('objects.id', ondelete='CASCADE'),
                  nullable=False),
        # name for this value (local to the object)
        sa.Column("name", sa.String(length=255), nullable=False),
        # value, as a JSON string
        sa.Column("value_json", sa.Text, nullable=False),
    )

    # Tables related to users
    # -----------------------

    # This table identifies individual users, and contains buildbot-specific
    # information about those users.
    users = sautils.Table(
        "users", metadata,
        # unique user id number
        sa.Column("uid", sa.Integer, primary_key=True),

        # identifier (nickname) for this user; used for display
        sa.Column("identifier", sa.String(255), nullable=False),

        # username portion of user credentials for authentication
        sa.Column("bb_username", sa.String(128)),

        # password portion of user credentials for authentication
        sa.Column("bb_password", sa.String(128)),
    )

    # This table stores information identifying a user that's related to a
    # particular interface - a version-control system, status plugin, etc.
    users_info = sautils.Table(
        "users_info", metadata,
        # unique user id number
        sa.Column('uid', sa.Integer,
                  sa.ForeignKey('users.uid', ondelete='CASCADE'),
                  nullable=False),

        # type of user attribute, such as 'git'
        sa.Column("attr_type", sa.String(128), nullable=False),

        # data for given user attribute, such as a commit string or password
        sa.Column("attr_data", sa.String(128), nullable=False),
    )

    # Tables related to masters
    # -------------------------

    masters = sautils.Table(
        "masters", metadata,
        # unique id per master
        sa.Column('id', sa.Integer, primary_key=True),

        # master's name (generally in the form hostname:basedir)
        sa.Column('name', sa.Text, nullable=False),
        # sha1 of name; used for a unique index
        sa.Column('name_hash', sa.String(hash_length), nullable=False),

        # true if this master is running
        sa.Column('active', sa.Integer, nullable=False),

        # updated periodically by a running master, so silently failed masters
        # can be detected by other masters
        sa.Column('last_active', sa.Integer, nullable=False),
    )

    # Indexes
    # -------

    sa.Index('buildrequests_buildsetid', buildrequests.c.buildsetid)
    sa.Index('buildrequests_builderid', buildrequests.c.builderid)
    sa.Index('buildrequests_complete', buildrequests.c.complete)
    sa.Index('build_properties_buildid', build_properties.c.buildid)
    sa.Index('build_data_buildid_name', build_data.c.buildid, build_data.c.name, unique=True)
    sa.Index('builds_buildrequestid', builds.c.buildrequestid)
    sa.Index('buildsets_complete', buildsets.c.complete)
    sa.Index('buildsets_submitted_at', buildsets.c.submitted_at)
    sa.Index('buildset_properties_buildsetid',
             buildset_properties.c.buildsetid)
    sa.Index('workers_name', workers.c.name, unique=True)
    sa.Index('changes_branch', changes.c.branch)
    sa.Index('changes_revision', changes.c.revision)
    sa.Index('changes_author', changes.c.author)
    sa.Index('changes_category', changes.c.category)
    sa.Index('changes_when_timestamp', changes.c.when_timestamp)
    sa.Index('change_files_changeid', change_files.c.changeid)
    sa.Index('change_properties_changeid', change_properties.c.changeid)
    sa.Index('changes_sourcestampid', changes.c.sourcestampid)
    sa.Index('changesource_name_hash', changesources.c.name_hash, unique=True)
    sa.Index('scheduler_name_hash', schedulers.c.name_hash, unique=True)
    sa.Index('scheduler_changes_schedulerid', scheduler_changes.c.schedulerid)
    sa.Index('scheduler_changes_changeid', scheduler_changes.c.changeid)
    sa.Index('scheduler_changes_unique', scheduler_changes.c.schedulerid,
             scheduler_changes.c.changeid, unique=True)
    sa.Index('builder_name_hash', builders.c.name_hash, unique=True)
    sa.Index('builder_masters_builderid', builder_masters.c.builderid)
    sa.Index('builder_masters_masterid', builder_masters.c.masterid)
    sa.Index('builder_masters_identity',
             builder_masters.c.builderid, builder_masters.c.masterid,
             unique=True)
    sa.Index('tag_name_hash', tags.c.name_hash, unique=True)
    sa.Index('builders_tags_builderid',
             builders_tags.c.builderid)
    sa.Index('builders_tags_unique',
             builders_tags.c.builderid,
             builders_tags.c.tagid,
             unique=True)
    sa.Index('configured_workers_buildmasterid',
             configured_workers.c.buildermasterid)
    sa.Index('configured_workers_workers', configured_workers.c.workerid)
    sa.Index('configured_workers_identity',
             configured_workers.c.buildermasterid,
             configured_workers.c.workerid, unique=True)
    sa.Index('connected_workers_masterid',
             connected_workers.c.masterid)
    sa.Index('connected_workers_workers', connected_workers.c.workerid)
    sa.Index('connected_workers_identity',
             connected_workers.c.masterid,
             connected_workers.c.workerid, unique=True)
    sa.Index('users_identifier', users.c.identifier, unique=True)
    sa.Index('users_info_uid', users_info.c.uid)
    sa.Index('users_info_uid_attr_type', users_info.c.uid,
             users_info.c.attr_type, unique=True)
    sa.Index('users_info_attrs', users_info.c.attr_type,
             users_info.c.attr_data, unique=True)
    sa.Index('change_users_changeid', change_users.c.changeid)
    sa.Index('users_bb_user', users.c.bb_username, unique=True)
    sa.Index('object_identity', objects.c.name, objects.c.class_name,
             unique=True)
    sa.Index('name_per_object', object_state.c.objectid, object_state.c.name,
             unique=True)
    sa.Index('master_name_hashes', masters.c.name_hash, unique=True)
    sa.Index('buildrequest_claims_brids', buildrequest_claims.c.brid,
             unique=True)
    sa.Index('sourcestamps_ss_hash_key', sourcestamps.c.ss_hash, unique=True)
    sa.Index('buildset_sourcestamps_buildsetid',
             buildset_sourcestamps.c.buildsetid)
    sa.Index('buildset_sourcestamps_unique',
             buildset_sourcestamps.c.buildsetid,
             buildset_sourcestamps.c.sourcestampid,
             unique=True)
    sa.Index('builds_number',
             builds.c.builderid, builds.c.number,
             unique=True)
    sa.Index('builds_workerid',
             builds.c.workerid)
    sa.Index('builds_masterid',
             builds.c.masterid)
    sa.Index('steps_number', steps.c.buildid, steps.c.number,
             unique=True)
    sa.Index('steps_name', steps.c.buildid, steps.c.name,
             unique=True)
    sa.Index('steps_started_at',
             steps.c.started_at)
    sa.Index('logs_slug', logs.c.stepid, logs.c.slug, unique=True)
    sa.Index('logchunks_firstline', logchunks.c.logid, logchunks.c.first_line)
    sa.Index('logchunks_lastline', logchunks.c.logid, logchunks.c.last_line)
    sa.Index('test_names_name', test_names.c.builderid, test_names.c.name,
             mysql_length={'name': 255})
    sa.Index('test_code_paths_path', test_code_paths.c.builderid, test_code_paths.c.path,
             mysql_length={'path': 255})

    # MySQL creates indexes for foreign keys, and these appear in the
    # reflection.  This is a list of (table, index) names that should be
    # expected on this platform

    implied_indexes = [
        ('change_users',
            dict(unique=False, column_names=['uid'], name='uid')),
        ('sourcestamps',
            dict(unique=False, column_names=['patchid'], name='patchid')),
        ('scheduler_masters',
            dict(unique=False, column_names=['masterid'], name='masterid')),
        ('changesource_masters',
            dict(unique=False, column_names=['masterid'], name='masterid')),
        ('buildset_sourcestamps',
            dict(unique=False, column_names=['sourcestampid'],
                 name='sourcestampid')),
        ('buildsets',
            dict(unique=False, column_names=['parent_buildid'],
                 name='parent_buildid')),
        ('builders_tags',
            dict(unique=False, column_names=['tagid'],
                 name='tagid')),
        ('changes',
            dict(unique=False, column_names=['parent_changeids'],
                 name='parent_changeids')),
        ('test_result_sets', {
            'name': 'builderid',
            'column_names': ['builderid'],
            'unique': False,
        }),
        ('test_result_sets', {
            'name': 'buildid',
            'column_names': ['buildid'],
            'unique': False,
        }),
        ('test_result_sets', {
            'name': 'stepid',
            'column_names': ['stepid'],
            'unique': False,
        }),
        ('test_results', {
            'name': 'test_result_setid',
            'column_names': ['test_result_setid'],
            'unique': False,
        }),
        ('test_results', {
            'name': 'test_code_pathid',
            'column_names': ['test_code_pathid'],
            'unique': False,
        }),
        ('test_results', {
            'name': 'builderid',
            'column_names': ['builderid'],
            'unique': False,
        }),
        ('test_results', {
            'name': 'test_nameid',
            'column_names': ['test_nameid'],
            'unique': False,
        }),
    ]

    # Migration support
    # -----------------

    # Buildbot has historically used 3 database migration systems:
    #  - homegrown system that used "version" table to track versions
    #  - SQLAlchemy-migrate that used "migrate_version" table to track versions
    #  - alembic that uses "alembic_version" table to track versions (current)
    # We need to detect each case and tell the user how to upgrade.

    config_path = util.sibpath(__file__, "migrations/alembic.ini")

    def table_exists(self, conn, table):
        try:
            r = conn.execute(f"select * from {table} limit 1")
            r.close()
            return True
        except Exception:
            return False

    def migrate_get_version(self, conn):
        r = conn.execute("select version from migrate_version limit 1")
        version = r.scalar()
        r.close()
        return version

    def alembic_get_scripts(self):
        alembic_config = alembic.config.Config(self.config_path)
        return alembic.script.ScriptDirectory.from_config(alembic_config)

    def alembic_stamp(self, conn, alembic_scripts, revision):
        context = alembic.runtime.migration.MigrationContext.configure(conn)
        context.stamp(alembic_scripts, revision)

    @defer.inlineCallbacks
    def is_current(self):
        def thd(conn):
            if not self.table_exists(conn, 'alembic_version'):
                return False

            alembic_scripts = self.alembic_get_scripts()
            current_script_rev_head = alembic_scripts.get_current_head()

            context = alembic.runtime.migration.MigrationContext.configure(conn)
            current_rev = context.get_current_revision()

            return current_rev == current_script_rev_head

        ret = yield self.db.pool.do(thd)
        return ret

    # returns a Deferred that returns None
    def create(self):
        # this is nice and simple, but used only for tests
        def thd(engine):
            self.metadata.create_all(bind=engine)
        return self.db.pool.do_with_engine(thd)

    @defer.inlineCallbacks
    def upgrade(self):

        # the upgrade process must run in a db thread
        def thd(conn):
            alembic_scripts = self.alembic_get_scripts()
            current_script_rev_head = alembic_scripts.get_current_head()

            if self.table_exists(conn, 'version'):
                raise UpgradeFromBefore0p9Error()

            if self.table_exists(conn, 'migrate_version'):
                version = self.migrate_get_version(conn)

                if version < 40:
                    raise UpgradeFromBefore0p9Error()

                last_sqlalchemy_migrate_version = 58
                if version != last_sqlalchemy_migrate_version:
                    raise UpgradeFromBefore3p0Error()

                self.alembic_stamp(conn, alembic_scripts, alembic_scripts.get_base())
                conn.execute('drop table migrate_version')

            if not self.table_exists(conn, 'alembic_version'):
                log.msg("Initializing empty database")

                # Do some tests first
                test_unicode(conn)

                Model.metadata.create_all(conn)
                self.alembic_stamp(conn, alembic_scripts, current_script_rev_head)
                return

            context = alembic.runtime.migration.MigrationContext.configure(conn)
            current_rev = context.get_current_revision()

            if current_rev == current_script_rev_head:
                log.msg('Upgrading database: the current database schema is already the newest')
                return

            log.msg('Upgrading database')
            with sautils.withoutSqliteForeignKeys(conn):
                with context.begin_transaction():
                    context.run_migrations()

            log.msg('Upgrading database: done')

        yield self.db.pool.do(thd)

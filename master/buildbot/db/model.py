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

import sqlalchemy as sa
import migrate
import migrate.versioning.schema
import migrate.versioning.repository
from twisted.python import util, log
from buildbot.db import base
from buildbot.db.types.json import JsonObject

try:
    from migrate.versioning import exceptions
    _hush_pyflakes = exceptions
except ImportError:
    from migrate import exceptions

class Model(base.DBConnectorComponent):
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
    #   use sa.Integer instead

    # build requests

    # A BuildRequest is a request for a particular build to be performed.  Each
    # BuildRequest is a part of a Buildset.  BuildRequests are claimed by
    # masters, to avoid multiple masters running the same build.
    buildrequests = sa.Table('buildrequests', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),
        sa.Column('buildsetid', sa.Integer, sa.ForeignKey("buildsets.id"),
            nullable=False),
        sa.Column('buildername', sa.String(length=256), nullable=False),
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
    )

    # Each row in this table represents a claimed build request, where the
    # claim is made by the object referenced by objectid.
    buildrequest_claims = sa.Table('buildrequest_claims', metadata,
        sa.Column('brid', sa.Integer, sa.ForeignKey('buildrequests.id'),
            nullable=False),
        sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
            index=True, nullable=True),
        sa.Column('claimed_at', sa.Integer, nullable=False),
    )

    # builds

    # This table contains basic information about each build.
    builds = sa.Table('builds', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),
        sa.Column('number', sa.Integer, nullable=False),
        sa.Column('builderid', sa.Integer, sa.ForeignKey('builders.id')),
        sa.Column('buildrequestid', sa.Integer, sa.ForeignKey('buildrequests.id'),
            nullable=False),
        # slave which performed this build
        # TODO: ForeignKey to buildslaves table, named buildslaveid
        # TODO: keep nullable to support slave-free builds
        sa.Column('buildslaveid', sa.Integer),
        # master which controlled this build
        sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
            nullable=False),
        # start/complete times
        sa.Column('started_at', sa.Integer, nullable=False),
        sa.Column('complete_at', sa.Integer),
        # a list of strings describing the build's state
        sa.Column('state_strings_json', sa.Text, nullable=False),
        sa.Column('results', sa.Integer),
    )

    # steps

    steps = sa.Table('steps', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('number', sa.Integer, nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('buildid', sa.Integer, sa.ForeignKey('builds.id')),
        sa.Column('started_at', sa.Integer, nullable=False),
        sa.Column('complete_at', sa.Integer),
        # a list of strings describing the step's state
        sa.Column('state_strings_json', sa.Text, nullable=False),
        sa.Column('results', sa.Integer),
        sa.Column('urls_json', sa.Text, nullable=False),
    )

    # logs

    logs = sa.Table('logs', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('stepid', sa.Integer, sa.ForeignKey('steps.id')),
        sa.Column('complete', sa.SmallInteger, nullable=False),
        sa.Column('num_lines', sa.Integer, nullable=False),
        # 's' = stdio, 't' = text, 'h' = html
        sa.Column('type', sa.String(1), nullable=False),
    )

    logchunks = sa.Table('logchunks', metadata,
        sa.Column('logid', sa.Integer, sa.ForeignKey('logs.id')),
        # 0-based line number range in this chunk (inclusive); note that for
        # HTML logs, this counts lines of HTML, not lines of rendered output
        sa.Column('first_line', sa.Integer, nullable=False),
        sa.Column('last_line', sa.Integer, nullable=False),
        # log contents, including a terminating newline, encoded in utf-8 or,
        # if 'compressed' is true, compressed with gzip
        sa.Column('content', sa.LargeBinary(65536)),
        sa.Column('compressed', sa.SmallInteger, nullable=False),
    )

    # buildsets

    # This table contains input properties for buildsets
    buildset_properties = sa.Table('buildset_properties', metadata,
        sa.Column('buildsetid', sa.Integer, sa.ForeignKey('buildsets.id'),
            nullable=False),
        sa.Column('property_name', sa.String(256), nullable=False),
        # JSON-encoded tuple of (value, source)
        sa.Column('property_value', sa.Text, nullable=False),
    )

    # This table represents Buildsets - sets of BuildRequests that share the
    # same original cause and source information.
    buildsets = sa.Table('buildsets', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),

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
    )

    # changesources

    # The changesources table gives a unique identifier to each ChangeSource.  It
    # also links to other tables used to ensure only one master runs each
    # changesource
    changesources = sa.Table('changesources', metadata,
        sa.Column("id", sa.Integer, primary_key=True),

        # name for this changesource, as given in the configuration, plus a hash
        # of that name used for a unique index
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('name_hash', sa.String(40), nullable=False),
    )

    # This links changesources to the master where they are running.  A changesource
    # linked to a master that is inactive can be unlinked by any master.  This
    # is a separate table so that we can "claim" changesources on a master by
    # inserting; this has better support in database servers for ensuring that
    # exactly one claim succeeds.
    changesource_masters = sa.Table('changesource_masters', metadata,
        sa.Column('changesourceid', sa.Integer, sa.ForeignKey('changesources.id'),
            nullable=False, primary_key=True),
        sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
            nullable=False),
    )

    # buildslaves
    buildslaves = sa.Table("buildslaves", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("info", JsonObject, nullable=False),
    )

    # link buildslaves to all builder/master pairs for which they are
    # configured
    configured_buildslaves = sa.Table('configured_buildslaves', metadata,
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('buildermasterid', sa.Integer,
            sa.ForeignKey('builder_masters.id'), nullable=False),
        sa.Column('buildslaveid', sa.Integer, sa.ForeignKey('buildslaves.id'),
            nullable=False),
    )

    # link buildslaves to the masters they are currently connected to
    connected_buildslaves = sa.Table('connected_buildslaves', metadata,
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('masterid', sa.Integer,
            sa.ForeignKey('masters.id'), nullable=False),
        sa.Column('buildslaveid', sa.Integer, sa.ForeignKey('buildslaves.id'),
            nullable=False),
    )

    # changes

    # Files touched in changes
    change_files = sa.Table('change_files', metadata,
        sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid'),
            nullable=False),
        sa.Column('filename', sa.String(1024), nullable=False),
    )

    # Properties for changes
    change_properties = sa.Table('change_properties', metadata,
        sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid'),
            nullable=False),
        sa.Column('property_name', sa.String(256), nullable=False),
        # JSON-encoded tuple of (value, source)
        sa.Column('property_value', sa.String(1024), nullable=False),
    )

    # users associated with this change; this allows multiple users for
    # situations where a version-control system can represent both an author
    # and committer, for example.
    change_users = sa.Table("change_users", metadata,
        sa.Column("changeid", sa.Integer, sa.ForeignKey('changes.changeid'),
            nullable=False),
        # uid for the author of the change with the given changeid
        sa.Column("uid", sa.Integer, sa.ForeignKey('users.uid'),
            nullable=False)
    )

    # Changes to the source code, produced by ChangeSources
    changes = sa.Table('changes', metadata,
        # changeid also serves as 'change number'
        sa.Column('changeid', sa.Integer,  primary_key=True),

        # author's name (usually an email address)
        sa.Column('author', sa.String(256), nullable=False),

        # commit comment
        sa.Column('comments', sa.Text, nullable=False),

        # old, CVS-related boolean
        sa.Column('is_dir', sa.SmallInteger, nullable=False), # old, for CVS

        # The branch where this change occurred.  When branch is NULL, that
        # means the main branch (trunk, master, etc.)
        sa.Column('branch', sa.String(256)),

        # revision identifier for this change
        sa.Column('revision', sa.String(256)), # CVS uses NULL

        sa.Column('revlink', sa.String(256)),

        # this is the timestamp of the change - it is usually copied from the
        # version-control system, and may be long in the past or even in the
        # future!
        sa.Column('when_timestamp', sa.Integer, nullable=False),

        # an arbitrary string used for filtering changes
        sa.Column('category', sa.String(256)),

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
            sa.ForeignKey('sourcestamps.id'))
    )

    # sourcestamps

    # Patches for SourceStamps that were generated through the try mechanism
    patches = sa.Table('patches', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),

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
    sourcestamps = sa.Table('sourcestamps', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),

        # hash of the branch, revision, patchid, repository, codebase, and
        # project, using hashColumns.
        sa.Column('ss_hash', sa.String(40), nullable=False),

        # the branch to check out.  When branch is NULL, that means
        # the main branch (trunk, master, etc.)
        sa.Column('branch', sa.String(256)),

        # the revision to check out, or the latest if NULL
        sa.Column('revision', sa.String(256)),

        # the patch to apply to generate this source code
        sa.Column('patchid', sa.Integer, sa.ForeignKey('patches.id')),

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
    buildset_sourcestamps = sa.Table('buildset_sourcestamps', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),
        sa.Column('buildsetid', sa.Integer,
            sa.ForeignKey('buildsets.id'),
            nullable=False),
        sa.Column('sourcestampid', sa.Integer,
            sa.ForeignKey('sourcestamps.id'),
            nullable=False),
    )

    # schedulers

    # The schedulers table gives a unique identifier to each scheduler.  It
    # also links to other tables used to ensure only one master runs each
    # scheduler, and to track changes that a scheduler may trigger a build for
    # later.
    schedulers = sa.Table('schedulers', metadata,
        sa.Column("id", sa.Integer, primary_key=True),

        # name for this scheduler, as given in the configuration, plus a hash
        # of that name used for a unique index
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('name_hash', sa.String(40), nullable=False),
    )

    # This links schedulers to the master where they are running.  A scheduler
    # linked to a master that is inactive can be unlinked by any master.  This
    # is a separate table so that we can "claim" schedulers on a master by
    # inserting; this has better support in database servers for ensuring that
    # exactly one claim succeeds.  The ID column is present for external users;
    # see bug #1053.
    scheduler_masters = sa.Table('scheduler_masters', metadata,
        sa.Column('schedulerid', sa.Integer, sa.ForeignKey('schedulers.id'),
            nullable=False, primary_key=True),
        sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
            nullable=False),
    )

    # This table references "classified" changes that have not yet been
    # "processed".  That is, the scheduler has looked at these changes and
    # determined that something should be done, but that hasn't happened yet.
    # Rows are deleted from this table as soon as the scheduler is done with
    # the change.
    scheduler_changes = sa.Table('scheduler_changes', metadata,
        sa.Column('schedulerid', sa.Integer, sa.ForeignKey('schedulers.id')),
        sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid')),
        # true (nonzero) if this change is important to this scheduler
        sa.Column('important', sa.Integer),
    )

    # builders

    builders = sa.Table('builders', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        # builder's name
        sa.Column('name', sa.Text, nullable=False),
        # sha1 of name; used for a unique index
        sa.Column('name_hash', sa.String(40), nullable=False),
    )

    # This links builders to the master where they are running.  A builder
    # linked to a master that is inactive can be unlinked by any master.  Note
    # that builders can run on multiple masters at the same time.
    builder_masters = sa.Table('builder_masters', metadata,
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('builderid', sa.Integer, sa.ForeignKey('builders.id'),
            nullable=False),
        sa.Column('masterid', sa.Integer, sa.ForeignKey('masters.id'),
            nullable=False),
    )

    # objects

    # This table uniquely identifies objects that need to maintain state across
    # invocations.
    objects = sa.Table("objects", metadata,
        # unique ID for this object
        sa.Column("id", sa.Integer, primary_key=True),
        # object's user-given name
        sa.Column('name', sa.String(128), nullable=False),
        # object's class name, basically representing a "type" for the state
        sa.Column('class_name', sa.String(128), nullable=False),
    )

    # This table stores key/value pairs for objects, where the key is a string
    # and the value is a JSON string.
    object_state = sa.Table("object_state", metadata,
        # object for which this value is set
        sa.Column("objectid", sa.Integer, sa.ForeignKey('objects.id'),
            nullable=False),
        # name for this value (local to the object)
        sa.Column("name", sa.String(length=256), nullable=False),
        # value, as a JSON string
        sa.Column("value_json", sa.Text, nullable=False),
    )

    #users

    # This table identifies individual users, and contains buildbot-specific
    # information about those users.
    users = sa.Table("users", metadata,
        # unique user id number
        sa.Column("uid", sa.Integer, primary_key=True),

        # identifier (nickname) for this user; used for display
        sa.Column("identifier", sa.String(256), nullable=False),

        # username portion of user credentials for authentication
        sa.Column("bb_username", sa.String(128)),

        # password portion of user credentials for authentication
        sa.Column("bb_password", sa.String(128)),
    )

    # This table stores information identifying a user that's related to a
    # particular interface - a version-control system, status plugin, etc.
    users_info = sa.Table("users_info", metadata,
        # unique user id number
        sa.Column("uid", sa.Integer, sa.ForeignKey('users.uid'),
                  nullable=False),

        # type of user attribute, such as 'git'
        sa.Column("attr_type", sa.String(128), nullable=False),

        # data for given user attribute, such as a commit string or password
        sa.Column("attr_data", sa.String(128), nullable=False),
    )

    # masters

    masters = sa.Table("masters", metadata,
        # unique id per master
        sa.Column('id', sa.Integer, primary_key=True),

        # master's name (generally in the form hostname:basedir)
        sa.Column('name', sa.Text, nullable=False),
        # sha1 of name; used for a unique index
        sa.Column('name_hash', sa.String(40), nullable=False),

        # true if this master is running
        sa.Column('active', sa.Integer, nullable=False),

        # updated periodically by a running master, so silently failed masters
        # can be detected by other masters
        sa.Column('last_active', sa.Integer, nullable=False),
    )

    # indexes

    sa.Index('buildrequests_buildsetid', buildrequests.c.buildsetid)
    sa.Index('buildrequests_buildername', buildrequests.c.buildername)
    sa.Index('buildrequests_complete', buildrequests.c.complete)
    sa.Index('builds_buildrequestid', builds.c.buildrequestid)
    sa.Index('buildsets_complete', buildsets.c.complete)
    sa.Index('buildsets_submitted_at', buildsets.c.submitted_at)
    sa.Index('buildset_properties_buildsetid',
            buildset_properties.c.buildsetid)
    sa.Index('buildslaves_name', buildslaves.c.name, unique=True)
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
    sa.Index('configured_slaves_buildmasterid',
            configured_buildslaves.c.buildermasterid)
    sa.Index('configured_slaves_slaves', configured_buildslaves.c.buildslaveid)
    sa.Index('configured_slaves_identity',
            configured_buildslaves.c.buildermasterid,
            configured_buildslaves.c.buildslaveid, unique=True)
    sa.Index('connected_slaves_masterid',
            connected_buildslaves.c.masterid)
    sa.Index('connected_slaves_slaves', connected_buildslaves.c.buildslaveid)
    sa.Index('connected_slaves_identity',
            connected_buildslaves.c.masterid,
            connected_buildslaves.c.buildslaveid, unique=True)
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
    sa.Index('builds_buildslaveid',
            builds.c.buildslaveid)
    sa.Index('builds_masterid',
            builds.c.masterid)
    sa.Index('steps_number', steps.c.buildid, steps.c.number,
            unique=True)
    sa.Index('steps_name', steps.c.buildid, steps.c.name,
            unique=True)
    sa.Index('logs_name', logs.c.stepid, logs.c.name, unique=True)
    sa.Index('logchunks_firstline', logchunks.c.logid, logchunks.c.first_line)
    sa.Index('logchunks_lastline', logchunks.c.logid, logchunks.c.last_line)

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
    ]

    #
    # migration support
    #

    # this is a bit more complicated than might be expected because the first
    # seven database versions were once implemented using a homespun migration
    # system, and we need to support upgrading masters from that system.  The
    # old system used a 'version' table, where SQLAlchemy-Migrate uses
    # 'migrate_version'

    repo_path = util.sibpath(__file__, "migrate")

    def is_current(self):
        def thd(engine):
            # we don't even have to look at the old version table - if there's
            # no migrate_version, then we're not up to date.
            repo = migrate.versioning.repository.Repository(self.repo_path)
            repo_version = repo.latest
            try:
                # migrate.api doesn't let us hand in an engine
                schema = migrate.versioning.schema.ControlledSchema(engine,
                                                                self.repo_path)
                db_version = schema.version
            except exceptions.DatabaseNotControlledError:
                return False

            return db_version == repo_version
        return self.db.pool.do_with_engine(thd)

    def upgrade(self):

        # here, things are a little tricky.  If we have a 'version' table, then
        # we need to version_control the database with the proper version
        # number, drop 'version', and then upgrade.  If we have no 'version'
        # table and no 'migrate_version' table, then we need to version_control
        # the database.  Otherwise, we just need to upgrade it.

        def table_exists(engine, tbl):
            try:
                r = engine.execute("select * from %s limit 1" % tbl)
                r.close()
                return True
            except:
                return False

        # http://code.google.com/p/sqlalchemy-migrate/issues/detail?id=100
        # means  we cannot use the migrate.versioning.api module.  So these
        # methods perform similar wrapping functions to what is done by the API
        # functions, but without disposing of the engine.
        def upgrade(engine):
            schema = migrate.versioning.schema.ControlledSchema(engine,
                    self.repo_path)
            changeset = schema.changeset(None)
            for version, change in changeset:
                log.msg('migrating schema version %s -> %d'
                        % (version, version + 1))
                schema.runchange(version, change, 1)

        def check_sqlalchemy_migrate_version():
            # sqlalchemy-migrate started including a version number in 0.7; we
            # support back to 0.6.1, but not 0.6.  We'll use some discovered
            # differences between 0.6.1 and 0.6 to get that resolution.
            version = getattr(migrate, '__version__', 'old')
            if version == 'old':
                try:
                    from migrate.versioning import schemadiff
                    if hasattr(schemadiff, 'ColDiff'):
                        version = "0.6.1"
                    else:
                        version = "0.6"
                except:
                    version = "0.0"
            version_tup = tuple(map(int, version.split('.')))
            log.msg("using SQLAlchemy-Migrate version %s" % (version,))
            if version_tup < (0,6,1):
                raise RuntimeError("You are using SQLAlchemy-Migrate %s. "
                    "The minimum version is 0.6.1." % (version,))

        def version_control(engine, version=None):
            migrate.versioning.schema.ControlledSchema.create(engine,
                    self.repo_path, version)

        # the upgrade process must run in a db thread
        def thd(engine):
            # if the migrate_version table exists, we can just let migrate
            # take care of this process.
            if table_exists(engine, 'migrate_version'):
                upgrade(engine)

            # if the version table exists, then we can version_control things
            # at that version, drop the version table, and let migrate take
            # care of the rest.
            elif table_exists(engine, 'version'):
                # get the existing version
                r = engine.execute("select version from version limit 1")
                old_version = r.scalar()

                # set up migrate at the same version
                version_control(engine, old_version)

                # drop the no-longer-required version table, using a dummy
                # metadata entry
                table = sa.Table('version', self.metadata,
                                 sa.Column('x', sa.Integer))
                table.drop(bind=engine)

                # clear the dummy metadata entry
                self.metadata.remove(table)

                # and, finally, upgrade using migrate
                upgrade(engine)

            # otherwise, this db is uncontrolled, so we just version control it
            # and update it.
            else:
                version_control(engine)
                upgrade(engine)

        # import the prerequisite classes for pickles
        check_sqlalchemy_migrate_version()
        return self.db.pool.do_with_engine(thd)

# migrate has a bug in one of its warnings; this is fixed in version control
# (3ba66abc4d), but not yet released. It can't hurt to fix it here, too, so we
# get realistic tracebacks
try:
    import migrate.versioning.exceptions as ex1
    import migrate.changeset.exceptions as ex2
    ex1.MigrateDeprecationWarning = ex2.MigrateDeprecationWarning
except (ImportError,AttributeError):
    pass

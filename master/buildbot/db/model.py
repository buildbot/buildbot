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

"""
Storage for the database model (schema)
"""

import sqlalchemy as sa
import migrate
import migrate.versioning.schema
import migrate.versioning.repository
from twisted.python import util, log
from buildbot.db import base

try:
    from migrate.versioning import exceptions
    _hush_pyflakes = exceptions
except ImportError:
    from migrate import exceptions

class Model(base.DBConnectorComponent):
    """
    DBConnector component to handle the database model; an instance is available
    at C{master.db.model}.

    This class has attributes for each defined table, as well as methods to
    handle schema migration (using sqlalchemy-migrate).  View the source to see
    the table definitions.

    Note that the Buildbot metadata is never bound to an engine, since that might
    lead users to execute queries outside of the thread pool.
    """

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

    # build requests

    buildrequests = sa.Table('buildrequests', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),
        sa.Column('buildsetid', sa.Integer, sa.ForeignKey("buildsets.id"), nullable=False),
        sa.Column('buildername', sa.String(length=256), nullable=False),
        sa.Column('priority', sa.Integer, nullable=False, server_default=sa.DefaultClause("0")), # TODO: used?

        # claimed_at is the time at which a master most recently asserted that
        # it is responsible for running the build: this will be updated
        # periodically to maintain the claim.  Note that 0 and NULL mean the
        # same thing here (and not 1969!)
        sa.Column('claimed_at', sa.Integer, server_default=sa.DefaultClause("0")),

        # claimed_by indicates which buildmaster has claimed this request. The
        # 'name' contains hostname/basedir, and will be the same for subsequent
        # runs of any given buildmaster. The 'incarnation' contains bootime/pid,
        # and will be different for subsequent runs. This allows each buildmaster
        # to distinguish their current claims, their old claims, and the claims
        # of other buildmasters, to treat them each appropriately.
        sa.Column('claimed_by_name', sa.String(length=256)),
        sa.Column('claimed_by_incarnation', sa.String(length=256)),

        # if this is zero, then the build is still pending
        sa.Column('complete', sa.Integer, server_default=sa.DefaultClause("0")), # TODO: boolean

        # results is only valid when complete == 1; 0 = SUCCESS, 1 = WARNINGS,
        # etc - see master/buildbot/status/builder.py
        sa.Column('results', sa.SmallInteger),

        # time the buildrequest was created
        sa.Column('submitted_at', sa.Integer, nullable=False),

        # time the buildrequest was completed, or NULL
        sa.Column('complete_at', sa.Integer),
    )
    """A BuildRequest is a request for a particular build to be performed.
    Each BuildRequest is a part of a BuildSet.  BuildRequests are claimed by
    masters, to avoid multiple masters running the same build."""

    # builds

    builds = sa.Table('builds', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),

        # XXX
        # the build number is local to the builder and (maybe?) the buildmaster
        sa.Column('number', sa.Integer, nullable=False),

        sa.Column('brid', sa.Integer, sa.ForeignKey('buildrequests.id'), nullable=False),
        sa.Column('start_time', sa.Integer, nullable=False),
        sa.Column('finish_time', sa.Integer),
    )
    """This table contains basic information about each build.  Note that most data
    about a build is still stored in on-disk pickles."""

    # buildsets

    buildset_properties = sa.Table('buildset_properties', metadata,
        sa.Column('buildsetid', sa.Integer, sa.ForeignKey('buildsets.id'), nullable=False),
        sa.Column('property_name', sa.String(256), nullable=False),
        # JSON-encoded tuple of (value, source)
        sa.Column('property_value', sa.String(1024), nullable=False), # TODO: too short?
    )
    """This table contains input properties for buildsets"""

    buildsets = sa.Table('buildsets', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),

        # a simple external identifier to track down this buildset later, e.g.,
        # for try requests
        sa.Column('external_idstring', sa.String(256)),

        # a short string giving the reason the buildset was created
        sa.Column('reason', sa.String(256)), # TODO: sa.Text
        sa.Column('sourcestampid', sa.Integer, sa.ForeignKey('sourcestamps.id'), nullable=False),
        sa.Column('submitted_at', sa.Integer, nullable=False), # TODO: redundant

        # if this is zero, then the build set is still pending
        sa.Column('complete', sa.SmallInteger, nullable=False, server_default=sa.DefaultClause("0")), # TODO: redundant
        sa.Column('complete_at', sa.Integer), # TODO: redundant

        # results is only valid when complete == 1; 0 = SUCCESS, 1 = WARNINGS,
        # etc - see master/buildbot/status/builder.py
        sa.Column('results', sa.SmallInteger), # TODO: synthesize from buildrequests
    )
    """This table represents BuildSets - sets of BuildRequests that share the same
    original cause and source information."""

    # changes

    change_files = sa.Table('change_files', metadata,
        sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid'), nullable=False),
        sa.Column('filename', sa.String(1024), nullable=False), # TODO: sa.Text
    )
    """Files touched in changes"""

    change_links = sa.Table('change_links', metadata,
        sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid'), nullable=False),
        sa.Column('link', sa.String(1024), nullable=False), # TODO: sa.Text
    )
    """Links (URLs) for changes"""

    change_properties = sa.Table('change_properties', metadata,
        sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid'), nullable=False),
        sa.Column('property_name', sa.String(256), nullable=False),
        # JSON-encoded tuple of (value, source)
        sa.Column('property_value', sa.String(1024), nullable=False), # TODO: too short?
    )
    """Properties for changes"""

    changes = sa.Table('changes', metadata,
        # changeid also serves as 'change number'
        sa.Column('changeid', sa.Integer,  primary_key=True), # TODO: rename to 'id'

        # author's name (usually an email address)
        sa.Column('author', sa.String(256), nullable=False),

        # commit comment
        sa.Column('comments', sa.String(1024), nullable=False), # TODO: too short?

        # old, CVS-related boolean
        sa.Column('is_dir', sa.SmallInteger, nullable=False), # old, for CVS

        # The branch where this change occurred.  When branch is NULL, that
        # means the main branch (trunk, master, etc.)
        sa.Column('branch', sa.String(256)),

        # revision identifier for this change
        sa.Column('revision', sa.String(256)), # CVS uses NULL

        # ?? (TODO)
        sa.Column('revlink', sa.String(256)),

        # this is the timestamp of the change - it is usually copied from the
        # version-control system, and may be long in the past or even in the
        # future!
        sa.Column('when_timestamp', sa.Integer, nullable=False),

        # an arbitrary string used for filtering changes
        sa.Column('category', sa.String(256)),

        # repository specifies, along with revision and branch, the
        # source tree in which this change was detected.
        sa.Column('repository', sa.String(length=512), nullable=False, server_default=''),

        # project names the project this source code represents.  It is used
        # later to filter changes
        sa.Column('project', sa.String(length=512), nullable=False, server_default=''),
    )
    """Changes to the source code, produced by ChangeSources"""

    # sourcestamps

    patches = sa.Table('patches', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),

        # number of directory levels to strip off (patch -pN)
        sa.Column('patchlevel', sa.Integer, nullable=False),

        # base64-encoded version of the patch file
        sa.Column('patch_base64', sa.Text, nullable=False),

        # subdirectory in which the patch should be applied; NULL for top-level
        sa.Column('subdir', sa.Text),
    )
    """Patches for SourceStamps that were generated through the try mechanism"""

    sourcestamp_changes = sa.Table('sourcestamp_changes', metadata,
        sa.Column('sourcestampid', sa.Integer, sa.ForeignKey('sourcestamps.id'), nullable=False),
        sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid'), nullable=False),
    )
    """The changes that led up to a particular source stamp."""
    # TODO: changes should be the result of the difference of two sourcestamps!

    sourcestamps = sa.Table('sourcestamps', metadata,
        sa.Column('id', sa.Integer,  primary_key=True),

        # the branch to check out.  When branch is NULL, that means
        # the main branch (trunk, master, etc.)
        sa.Column('branch', sa.String(256)),

        # the revision to check out, or the latest if NULL
        sa.Column('revision', sa.String(256)),

        # the patch to apply to generate this source code
        sa.Column('patchid', sa.Integer, sa.ForeignKey('patches.id')),

        # the repository from which this source should be checked out
        sa.Column('repository', sa.String(length=512), nullable=False, server_default=''),

        # the project this source code represents
        sa.Column('project', sa.String(length=512), nullable=False, server_default=''),
    )
    """A sourcestamp identifies a particular instance of the source code.
    Ideally, this would always be absolute, but in practice source stamps can
    also mean "latest" (when revision is NULL), which is of course a
    time-dependent definition."""

    # schedulers

    scheduler_changes = sa.Table('scheduler_changes', metadata,
        sa.Column('schedulerid', sa.Integer, sa.ForeignKey('schedulers.schedulerid')),
        sa.Column('changeid', sa.Integer, sa.ForeignKey('changes.changeid')),
        # true if this change is important to this scheduler
        sa.Column('important', sa.SmallInteger), # TODO: Boolean
    )
    """This table references "classified" changes that have not yet been "processed".
    That is, the scheduler has looked at these changes and determined that
    something should be done, but that hasn't happened yet.  Rows are deleted
    from this table as soon as the scheduler is done with the change."""

    scheduler_upstream_buildsets = sa.Table('scheduler_upstream_buildsets', metadata,
        sa.Column('buildsetid', sa.Integer, sa.ForeignKey('buildsets.id')),
        sa.Column('schedulerid', sa.Integer, sa.ForeignKey('schedulers.schedulerid')),
        # true if this buildset is still active
        sa.Column('active', sa.SmallInteger), # TODO: redundant
    )
    """This table references buildsets in which a particular scheduler is
    interested.  On every run, a scheduler checks its upstream buildsets for
    completion and reacts accordingly.  Records are never deleted from this
    table, but active is set to 0 when the record is no longer necessary."""
    # TODO: delete records eventually

    schedulers = sa.Table("schedulers", metadata,
        # unique ID for scheduler
        sa.Column('schedulerid', sa.Integer, primary_key=True), # TODO: rename to id
        # scheduler's name in master.cfg
        sa.Column('name', sa.String(128), nullable=False),
        # JSON-encoded state for this scheduler
        sa.Column('state', sa.String(1024), nullable=False),
        # scheduler's class name, basically representing a "type" for the state
        sa.Column('class_name', sa.String(128), nullable=False),
    )
    """This table records the "state" for each scheduler.  This state is, at least,
    the last change that was analyzed, but is stored in an opaque JSON object.
    Note that schedulers are never deleted."""
    # TODO: delete records eventually

    objects = sa.Table("objects", metadata,
        # unique ID for this object
        sa.Column("id", sa.Integer, primary_key=True),
        # object's user-given name
        sa.Column('name', sa.String(128), nullable=False),
        # object's class name, basically representing a "type" for the state
        sa.Column('class_name', sa.String(128), nullable=False),

        # prohibit multiple id's for the same object
        sa.UniqueConstraint('name', 'class_name', name='object_identity'),
    )
    """This table uniquely identifies objects that need to maintain state
    across invocations."""

    object_state = sa.Table("object_state", metadata,
        # object for which this value is set
        sa.Column("objectid", sa.Integer, sa.ForeignKey('objects.id'),
            nullable=False),
        # name for this value (local to the object)
        sa.Column("name", sa.String(length=256), nullable=False),
        # value, as a JSON string
        sa.Column("value_json", sa.Text, nullable=False),

        # prohibit multiple values for the same object and name
        sa.UniqueConstraint('objectid', 'name', name='name_per_object'),
    )
    """This table stores key/value pairs for objects, where the key is a string
    and the value is a JSON string."""

    # indexes

    sa.Index('name_and_class', schedulers.c.name, schedulers.c.class_name)
    sa.Index('buildrequests_buildsetid', buildrequests.c.buildsetid)
    sa.Index('buildrequests_buildername', buildrequests.c.buildername)
    sa.Index('buildrequests_complete', buildrequests.c.complete)
    sa.Index('buildrequests_claimed_at', buildrequests.c.claimed_at)
    sa.Index('buildrequests_claimed_by_name', buildrequests.c.claimed_by_name)
    sa.Index('builds_number', builds.c.number)
    sa.Index('builds_brid', builds.c.brid)
    sa.Index('buildsets_complete', buildsets.c.complete)
    sa.Index('buildsets_submitted_at', buildsets.c.submitted_at)
    sa.Index('buildset_properties_buildsetid', buildset_properties.c.buildsetid)
    sa.Index('changes_branch', changes.c.branch)
    sa.Index('changes_revision', changes.c.revision)
    sa.Index('changes_author', changes.c.author)
    sa.Index('changes_category', changes.c.category)
    sa.Index('changes_when_timestamp', changes.c.when_timestamp)
    sa.Index('change_files_changeid', change_files.c.changeid)
    sa.Index('change_links_changeid', change_links.c.changeid)
    sa.Index('change_properties_changeid', change_properties.c.changeid)
    sa.Index('scheduler_changes_schedulerid', scheduler_changes.c.schedulerid)
    sa.Index('scheduler_changes_changeid', scheduler_changes.c.changeid)
    sa.Index('scheduler_changes_unique', scheduler_changes.c.schedulerid,
                    scheduler_changes.c.changeid, unique=True)
    sa.Index('scheduler_upstream_buildsets_buildsetid', scheduler_upstream_buildsets.c.buildsetid)
    sa.Index('scheduler_upstream_buildsets_schedulerid', scheduler_upstream_buildsets.c.schedulerid)
    sa.Index('scheduler_upstream_buildsets_active', scheduler_upstream_buildsets.c.active)
    sa.Index('sourcestamp_changes_sourcestampid', sourcestamp_changes.c.sourcestampid)

    #
    # migration support
    #

    # this is a bit more complicated than might be expected because the first
    # seven database versions were once implemented using a homespun migration
    # system, and we need to support upgrading masters from that system.  The
    # old system used a 'version' table, where SQLAlchemy-Migrate uses
    # 'migrate_version'

    repo_path = util.sibpath(__file__, "migrate")
    "path to the SQLAlchemy-Migrate 'repository'"

    def is_current(self):
        """Returns true (via deferred) if the database's version is up to date."""
        def thd(engine):
            # we don't even have to look at the old version table - if there's
            # no migrate_version, then we're not up to date.
            repo = migrate.versioning.repository.Repository(self.repo_path)
            repo_version = repo.latest
            try:
                # migrate.api doesn't let us hand in an engine
                schema = migrate.versioning.schema.ControlledSchema(engine, self.repo_path)
                db_version = schema.version
            except exceptions.DatabaseNotControlledError:
                return False

            return db_version == repo_version
        return self.db.pool.do_with_engine(thd)

    def upgrade(self):
        """Upgrade the database to the most recent schema version, returning a
        deferred."""

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

        # due to http://code.google.com/p/sqlalchemy-migrate/issues/detail?id=100, we cannot
        # use the migrate.versioning.api module.  So these methods perform similar wrapping
        # functions to what is done by the API functions, but without disposing of the engine.
        def upgrade(engine):
            schema = migrate.versioning.schema.ControlledSchema(engine, self.repo_path)
            changeset = schema.changeset(None)
            for version, change in changeset:
                log.msg('migrating schema version %s -> %d'
                        % (version, version + 1))
                schema.runchange(version, change, 1)

        def version_control(engine, version=None):
            migrate.versioning.schema.ControlledSchema.create(engine, self.repo_path, version)

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

                # and, finally, upgrade using migrate
                upgrade(engine)

            # otherwise, this db is uncontrolled, so we just version control it
            # and update it.
            else:
                version_control(engine)
                upgrade(engine)
        return self.db.pool.do_with_engine(thd)

# migrate has a bug in one of its warnings; this is fixed in version control
# (3ba66abc4d), but not yet released. It can't hurt to fix it here, too, so we
# get realistic tracebacks
try:
    import migrate.versioning.exceptions as ex1
    import migrate.changeset.exceptions as ex2
    ex1.MigrateDeprecationWarning = ex2.MigrateDeprecationWarning
except ImportError:
    pass

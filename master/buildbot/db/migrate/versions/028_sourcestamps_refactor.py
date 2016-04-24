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

import hashlib
import time

import sqlalchemy as sa

from buildbot.util import sautils


def rename_sourcestamps_to_old(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sourcestamps = sautils.Table('sourcestamps', metadata,
                                 sa.Column('id', sa.Integer, primary_key=True),
                                 sa.Column('branch', sa.String(256)),
                                 sa.Column('revision', sa.String(256)),
                                 sa.Column(
                                     'patchid', sa.Integer, sa.ForeignKey('patches.id')),
                                 sa.Column('repository', sa.String(length=512), nullable=False,
                                           server_default=''),
                                 sa.Column('codebase', sa.String(256), nullable=False,
                                           server_default=sa.DefaultClause("")),
                                 sa.Column('project', sa.String(length=512), nullable=False,
                                           server_default=''),
                                 sa.Column('sourcestampsetid', sa.Integer,
                                           sa.ForeignKey('sourcestampsets.id')),
                                 )

    for index in sourcestamps.indexes:
        index.drop()
    migrate_engine.execute('alter table sourcestamps '
                           'rename to sourcestamps_old')


def add_new_schema_parts(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # add new sourcestamps table, with proper indexing
    sautils.Table('patches', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  # ...
                  )
    sourcestamps = sautils.Table(
        'sourcestamps', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('ss_hash', sa.String(40), nullable=False),
        sa.Column('branch', sa.String(256)),
        sa.Column('revision', sa.String(256)),
        sa.Column('patchid', sa.Integer, sa.ForeignKey('patches.id')),
        sa.Column('repository', sa.String(length=512), nullable=False,
                  server_default=''),
        sa.Column('codebase', sa.String(256), nullable=False,
                  server_default=sa.DefaultClause("")),
        sa.Column('project', sa.String(length=512), nullable=False,
                  server_default=''),
        sa.Column('created_at', sa.Integer, nullable=False),
    )
    sourcestamps.create()

    idx = sa.Index('sourcestamps_ss_hash_key',
                   sourcestamps.c.ss_hash, unique=True)
    idx.create()

    changes = sautils.Table(
        'changes', metadata,
        sa.Column('changeid', sa.Integer, primary_key=True),
        sa.Column('author', sa.String(256), nullable=False),
        sa.Column('comments', sa.String(1024), nullable=False),
        sa.Column('is_dir', sa.SmallInteger, nullable=False),
        sa.Column('branch', sa.String(256)),
        sa.Column('revision', sa.String(256)),
        sa.Column('revlink', sa.String(256)),
        sa.Column('when_timestamp', sa.Integer, nullable=False),
        sa.Column('category', sa.String(256)),
        sa.Column('repository', sa.String(length=512), nullable=False,
                  server_default=''),
        sa.Column('codebase', sa.String(256), nullable=False,
                  server_default=sa.DefaultClause("")),
        sa.Column('project', sa.String(length=512), nullable=False,
                  server_default=''),
    )
    sourcestampid = sa.Column('sourcestampid', sa.Integer,
                              sa.ForeignKey('sourcestamps.id'))
    sourcestampid.create(changes, populate_default=True)

    # re-create all indexes on the table - sqlite dropped them
    if migrate_engine.dialect.name == 'sqlite':
        idx = sa.Index('changes_branch', changes.c.branch)
        idx.create()
        idx = sa.Index('changes_revision', changes.c.revision)
        idx.create()
        idx = sa.Index('changes_author', changes.c.author)
        idx.create()
        idx = sa.Index('changes_category', changes.c.category)
        idx.create()
        idx = sa.Index('changes_when_timestamp', changes.c.when_timestamp)
        idx.create()

    # but this index is new:
    idx = sa.Index('changes_sourcestampid', changes.c.sourcestampid)
    idx.create()


def migrate_data(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sourcestamps = sautils.Table('sourcestamps', metadata,
                                 sa.Column('id', sa.Integer, primary_key=True),
                                 sa.Column(
                                     'ss_hash', sa.String(40), nullable=False, unique=True),
                                 sa.Column('branch', sa.String(256)),
                                 sa.Column('revision', sa.String(256)),
                                 sa.Column(
                                     'patchid', sa.Integer, sa.ForeignKey('patches.id')),
                                 sa.Column('repository', sa.String(length=512), nullable=False,
                                           server_default=''),
                                 sa.Column('codebase', sa.String(256), nullable=False,
                                           server_default=sa.DefaultClause("")),
                                 sa.Column('project', sa.String(length=512), nullable=False,
                                           server_default=''),
                                 sa.Column(
                                     'created_at', sa.Integer, nullable=False),
                                 )

    # define a select-or-insert function, similar to that for the sourcestamp
    # connector
    def hashColumns(*args):
        # copied from master/buildbot/db/base.py
        def encode(x):
            try:
                return x.encode('utf8')
            except AttributeError:
                if x is None:
                    return '\xf5'
                return str(x)
        return hashlib.sha1('\0'.join(map(encode, args))).hexdigest()

    def findSourceStampId(branch=None, revision=None, repository=None,
                          project=None, codebase=None, patchid=None):
        tbl = sourcestamps

        ss_hash = hashColumns(branch, revision, repository, project,
                              codebase, patchid)

        q = sa.select([tbl.c.id], whereclause=tbl.c.ss_hash == ss_hash)
        r = migrate_engine.execute(q)
        row = r.fetchone()
        r.close()

        if row:
            return row.id

        r = migrate_engine.execute(tbl.insert(), [{
            'branch': branch,
            'revision': revision,
            'repository': repository,
            'codebase': codebase,
            'project': project,
            'patchid': patchid,
            'ss_hash': ss_hash,
            'created_at': time.time(),
        }])
        return r.inserted_primary_key[0]

    # set up the tables we'll need to migrate
    sourcestamps_old = sautils.Table('sourcestamps_old', metadata,
                                     sa.Column(
                                         'id', sa.Integer, primary_key=True),
                                     sa.Column('branch', sa.String(256)),
                                     sa.Column('revision', sa.String(256)),
                                     sa.Column(
                                         'patchid', sa.Integer, sa.ForeignKey('patches.id')),
                                     sa.Column('repository', sa.String(length=512), nullable=False,
                                               server_default=''),
                                     sa.Column('codebase', sa.String(256), nullable=False,
                                               server_default=sa.DefaultClause("")),
                                     sa.Column('project', sa.String(length=512), nullable=False,
                                               server_default=''),
                                     sa.Column('sourcestampsetid', sa.Integer,
                                               sa.ForeignKey('sourcestampsets.id')),
                                     )
    changes = sautils.Table('changes', metadata,
                            sa.Column(
                                'changeid', sa.Integer, primary_key=True),
                            sa.Column(
                                'author', sa.String(256), nullable=False),
                            sa.Column(
                                'comments', sa.String(1024), nullable=False),
                            sa.Column(
                                'is_dir', sa.SmallInteger, nullable=False),
                            sa.Column('branch', sa.String(256)),
                            sa.Column('revision', sa.String(256)),
                            sa.Column('revlink', sa.String(256)),
                            sa.Column(
                                'when_timestamp', sa.Integer, nullable=False),
                            sa.Column('category', sa.String(256)),
                            sa.Column('repository', sa.String(length=512), nullable=False,
                                      server_default=''),
                            sa.Column('codebase', sa.String(256), nullable=False,
                                      server_default=sa.DefaultClause("")),
                            sa.Column('project', sa.String(length=512), nullable=False,
                                      server_default=''),
                            sa.Column('sourcestampid', sa.Integer,
                                      sa.ForeignKey('sourcestamps.id'))
                            )

    # invent a new sourcestamp for each change
    c = changes.c
    q = sa.select([c.changeid, c.branch, c.revision, c.project,
                   c.codebase, c.repository])
    for row in migrate_engine.execute(q).fetchall():
        ssid = findSourceStampId(branch=row.branch, revision=row.revision,
                                 project=row.project, codebase=row.codebase,
                                 repository=row.repository, patchid=None)
        migrate_engine.execute(
            changes.update(whereclause=(changes.c.changeid == row.changeid)),
            sourcestampid=ssid)

    # add buildset_sourcestamps table
    buildsets = sautils.Table('buildsets', metadata,
                              sa.Column('id', sa.Integer, primary_key=True),
                              sa.Column('external_idstring', sa.String(256)),
                              sa.Column('reason', sa.String(256)),
                              sa.Column(
                                  'submitted_at', sa.Integer, nullable=False),
                              sa.Column('complete', sa.SmallInteger, nullable=False,
                                        server_default=sa.DefaultClause("0")),
                              sa.Column('complete_at', sa.Integer),
                              sa.Column('results', sa.SmallInteger),
                              sa.Column('sourcestampsetid', sa.Integer,
                                        sa.ForeignKey('sourcestampsets.id')),
                              )

    buildset_sourcestamps = sautils.Table(
        'buildset_sourcestamps', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('buildsetid', sa.Integer,
                  sa.ForeignKey('buildsets.id'),
                  nullable=False),
        sa.Column('sourcestampid', sa.Integer,
                  sa.ForeignKey('sourcestamps.id'),
                  nullable=False),
    )
    buildset_sourcestamps.create()
    idx = sa.Index('buildset_sourcestamps_buildsetid',
                   buildset_sourcestamps.c.buildsetid)
    idx.create()
    idx = sa.Index('buildset_sourcestamps_unique',
                   buildset_sourcestamps.c.buildsetid,
                   buildset_sourcestamps.c.sourcestampid,
                   unique=True)
    idx.create()

    # now translate the existing buildset -> sourcestampset relationships into
    # buildset -> buildset_sourcestamps
    f = buildsets.join(
        sourcestamps_old,
        onclause=sourcestamps_old.c.sourcestampsetid == buildsets.c.sourcestampsetid)
    ss = sourcestamps_old
    q = sa.select([buildsets.c.id, ss.c.branch, ss.c.revision,
                   ss.c.project, ss.c.codebase, ss.c.repository, ss.c.patchid],
                  from_obj=[f])
    r = migrate_engine.execute(q)
    for row in r.fetchall():
        ssid = findSourceStampId(branch=row.branch, revision=row.revision,
                                 project=row.project, codebase=row.codebase,
                                 repository=row.repository, patchid=row.patchid)
        migrate_engine.execute(buildset_sourcestamps.insert(),
                               buildsetid=row.id, sourcestampid=ssid)


def drop_old_schema_parts(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sourcestamp_changes = sautils.Table('sourcestamp_changes', metadata,
                                        sa.Column('sourcestampid', sa.Integer),
                                        # ...
                                        )
    # this drops 'sourcestamp_changes_sourcestampid' too
    sourcestamp_changes.drop()

    buildsets = sautils.Table('buildsets', metadata,
                              sa.Column('id', sa.Integer, primary_key=True),
                              sa.Column('external_idstring', sa.String(256)),
                              sa.Column('reason', sa.String(256)),
                              sa.Column(
                                  'submitted_at', sa.Integer, nullable=False),
                              sa.Column('complete', sa.SmallInteger, nullable=False,
                                        server_default=sa.DefaultClause("0")),
                              sa.Column('complete_at', sa.Integer),
                              sa.Column('results', sa.SmallInteger),
                              sa.Column('sourcestampsetid', sa.Integer),
                              )

    # there's a leftover bogus foreign key constraint referencing
    # sourcestamps_old.sourcestampid, from the rename of sourcestampid to
    # sourcestampsetid in migration 018.  Dropping this column will drop
    # that constraint, too.
    buildsets.c.sourcestampsetid.drop()

    sourcestamps_old = sautils.Table('sourcestamps_old', metadata,
                                     sa.Column(
                                         'id', sa.Integer, primary_key=True),
                                     # ...
                                     )
    sourcestamps_old.drop()

    sourcestampsets = sautils.Table('sourcestampsets', metadata,
                                    sa.Column(
                                        'id', sa.Integer, primary_key=True),
                                    )
    sourcestampsets.drop()

    # re-create all indexes on the table - sqlite dropped them
    if migrate_engine.dialect.name == 'sqlite':
        idx = sa.Index('buildsets_complete', buildsets.c.complete)
        idx.create()
        idx = sa.Index('buildsets_submitted_at', buildsets.c.submitted_at)
        idx.create()


def upgrade(migrate_engine):
    # Begin by renaming the sourcestamps table to sourcestamps_old.  The new
    # table has the same columns (except sourcestampsetid), but has a unique
    # index over all of the interesting columns, so all of the ids will change.
    rename_sourcestamps_to_old(migrate_engine)

    # add a 'sourcestampid' column to changes
    add_new_schema_parts(migrate_engine)

    # migrate the data to new tables
    migrate_data(migrate_engine)

    # finally, drop the old tables
    drop_old_schema_parts(migrate_engine)

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

import migrate
import sqlalchemy as sa

from buildbot.db import NULL
from buildbot.util import sautils


def migrate_claims(migrate_engine, metadata, buildrequests, objects,
                   buildrequest_claims):

    # First, ensure there is an object row for each master
    null_id = sa.null().label('id')
    if migrate_engine.dialect.name == 'postgresql':
        # postgres needs NULL cast to an integer:
        null_id = sa.cast(null_id, sa.INTEGER)
    new_objects = sa.select([
        null_id,
        buildrequests.c.claimed_by_name.label("name"),
        sa.literal_column("'BuildMaster'").label("class_name"),
    ],
        whereclause=buildrequests.c.claimed_by_name != NULL,
        distinct=True)

    # this doesn't seem to work without str() -- verified in sqla 0.6.0 - 0.7.1
    migrate_engine.execute(
        str(sautils.InsertFromSelect(objects, new_objects)))

    # now make a buildrequest_claims row for each claimed build request
    join = buildrequests.join(
        objects, (buildrequests.c.claimed_by_name == objects.c.name) &
        # (have to use sa.text because str, below, doesn't work
        # with placeholders)
        (objects.c.class_name == sa.text("'BuildMaster'")))
    claims = sa.select([
        buildrequests.c.id.label('brid'),
        objects.c.id.label('objectid'),
        buildrequests.c.claimed_at,
    ], from_obj=[join],
        whereclause=buildrequests.c.claimed_by_name != NULL)
    migrate_engine.execute(
        str(sautils.InsertFromSelect(buildrequest_claims, claims)))


def drop_columns(metadata, buildrequests):
    # sqlalchemy-migrate <0.7.0 has a bug with sqlalchemy >=0.7.0, where
    # it tries to change an immutable column; this is the workaround, from
    # http://code.google.com/p/sqlalchemy-migrate/issues/detail?id=112
    if not sa.__version__.startswith('0.6.'):
        if not hasattr(migrate, '__version__'):  # that is, older than 0.7
            buildrequests.columns = buildrequests._columns

    buildrequests.c.claimed_at.drop()
    buildrequests.c.claimed_by_name.drop()
    buildrequests.c.claimed_by_incarnation.drop()


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # a copy of the buildrequests table, but with the foreign keys stripped
    buildrequests = sautils.Table('buildrequests', metadata,
                                  sa.Column(
                                      'id', sa.Integer, primary_key=True),
                                  sa.Column(
                                      'buildsetid', sa.Integer, nullable=False),
                                  sa.Column(
                                      'buildername', sa.String(length=256), nullable=False),
                                  sa.Column('priority', sa.Integer, nullable=False,
                                            server_default=sa.DefaultClause("0")),
                                  sa.Column('claimed_at', sa.Integer,
                                            server_default=sa.DefaultClause("0")),
                                  sa.Column(
                                      'claimed_by_name', sa.String(length=256)),
                                  sa.Column(
                                      'claimed_by_incarnation', sa.String(length=256)),
                                  sa.Column('complete', sa.Integer,
                                            server_default=sa.DefaultClause("0")),
                                  sa.Column('results', sa.SmallInteger),
                                  sa.Column(
                                      'submitted_at', sa.Integer, nullable=False),
                                  sa.Column('complete_at', sa.Integer),
                                  )

    # existing objects table, used as a foreign key
    objects = sautils.Table("objects", metadata,
                            # unique ID for this object
                            sa.Column("id", sa.Integer, primary_key=True),
                            # object's user-given name
                            sa.Column('name', sa.String(128), nullable=False),
                            # object's class name, basically representing a
                            # "type" for the state
                            sa.Column(
                                'class_name', sa.String(128), nullable=False),

                            # prohibit multiple id's for the same object
                            sa.UniqueConstraint(
                                'name', 'class_name', name='object_identity'),
                            )

    # and a new buildrequest_claims table
    buildrequest_claims = sautils.Table(
        'buildrequest_claims', metadata,
        sa.Column('brid', sa.Integer, sa.ForeignKey('buildrequests.id'),
                  index=True, unique=True),
        sa.Column('objectid', sa.Integer, sa.ForeignKey('objects.id'),
                  index=True, nullable=True),
        sa.Column('claimed_at', sa.Integer, nullable=False),
    )

    # create the new table
    buildrequest_claims.create()

    # migrate the claims into that table
    migrate_claims(migrate_engine, metadata, buildrequests,
                   objects, buildrequest_claims)

    # and drop the claim-related columns in buildrequests
    drop_columns(metadata, buildrequests)

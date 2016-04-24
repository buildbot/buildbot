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

import sqlalchemy as sa

from buildbot.util import sautils


def rename_buildrequest_claims(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    buildrequest_claims = sautils.Table("buildrequest_claims", metadata,
                                        sa.Column(
                                            'brid', sa.Integer, index=True, unique=True),
                                        sa.Column(
                                            'objectid', sa.Integer, index=True, nullable=True),
                                        sa.Column(
                                            'claimed_at', sa.Integer, nullable=False),
                                        )
    for index in buildrequest_claims.indexes:
        index.drop()
    migrate_engine.execute('alter table buildrequest_claims '
                           'rename to buildrequest_claims_old')


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sautils.Table('buildrequests', metadata,
                  sa.Column('id', sa.Integer, primary_key=True),
                  # ..
                  )

    objects = sautils.Table("objects", metadata,
                            sa.Column("id", sa.Integer, primary_key=True),
                            sa.Column('name', sa.String(128), nullable=False),
                            sa.Column(
                                'class_name', sa.String(128), nullable=False),
                            )

    masters = sautils.Table(
        "masters", metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('name_hash', sa.String(40), nullable=False),
        sa.Column('active', sa.Integer, nullable=False),
        sa.Column('last_active', sa.Integer, nullable=False),
    )

    buildrequest_claims_old = sautils.Table(
        "buildrequest_claims_old", metadata,
        sa.Column('brid', sa.Integer, index=True),
        sa.Column('objectid', sa.Integer, index=True, nullable=True),
        sa.Column('claimed_at', sa.Integer, nullable=False),
    )

    buildrequest_claims = sautils.Table(
        'buildrequest_claims', metadata,
        sa.Column('brid', sa.Integer, sa.ForeignKey(
            'buildrequests.id'), nullable=False),
        sa.Column('masterid', sa.Integer, sa.ForeignKey(
            'masters.id'), index=True, nullable=True),
        sa.Column('claimed_at', sa.Integer, nullable=False),
    )

    # create the new table
    masters.create()

    # migrate buildrequest_claims..
    #
    # buildrequest claims currently point to master objects in the objects
    # table, but we want them to point to masters, instead.  So, we set up
    # a mapping from objectid to masterid, then replace the table using
    # that mapping.

    # rename buildrequest_claims to buildrequest_claims_old
    rename_buildrequest_claims(migrate_engine)

    # insert master rows, and capture the id mapping
    idmap = {}  # objectid : masterid
    r = migrate_engine.execute(sa.select([objects.c.id, objects.c.name],
                                         whereclause=(objects.c.class_name == u'buildbot.master.BuildMaster')))
    for row in r.fetchall():
        r = migrate_engine.execute(masters.insert(),
                                   name=row.name,
                                   name_hash=hashlib.sha1(
                                       row.name).hexdigest(),
                                   active=0,
                                   last_active=0)
        masterid = r.inserted_primary_key[0]
        idmap[row.id] = masterid

    # copy data from old to new, using the mapping
    buildrequest_claims.create()
    if idmap:
        case_stmt = sa.cast(
            sa.case(value=buildrequest_claims_old.c.objectid,
                    whens=idmap,
                    else_=None), sa.Integer).label('masterid')
    else:
        case_stmt = sa.text('NULL')
    buildrequests_with_masterid = sa.select(
        [buildrequest_claims_old.c.brid,
         case_stmt,
         buildrequest_claims_old.c.claimed_at])
    migrate_engine.execute(sautils.InsertFromSelect(
        buildrequest_claims, buildrequests_with_masterid))

    # drop the old table
    buildrequest_claims_old.drop()

    # add the indices
    sa.Index('master_name_hashes', masters.c.name_hash,
             unique=True).create()
    sa.Index('buildrequest_claims_brids', buildrequest_claims.c.brid,
             unique=True).create()

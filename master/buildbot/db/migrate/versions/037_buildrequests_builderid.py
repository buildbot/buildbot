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
from migrate import changeset

from buildbot.util import sautils


def add_new_schema_parts(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine
    sautils.Table('builders', metadata, autoload=True)
    sautils.Table('buildsets', metadata, autoload=True)

    buildrequests = sautils.Table('buildrequests', metadata, autoload=True)

    builderid = sa.Column(
        'builderid', sa.Integer, sa.ForeignKey('builders.id'))
    builderid.create(buildrequests)

    # Remove all index
    for index in buildrequests.indexes:
        index.drop()


def migrate_data(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # set up the tables we'll need to migrate
    buildrequests = sautils.Table('buildrequests', metadata, autoload=True)
    builders = sautils.Table('builders', metadata, autoload=True)

    bName2bID = dict()
    q = sa.select([builders.c.id, builders.c.name])
    for row in migrate_engine.execute(q).fetchall():
        bName2bID[row.name] = row.id

    def hashColumns(*args):
        # copy paste from buildbot/db/base.py
        def encode(x):
            try:
                return x.encode('utf8')
            except AttributeError:
                if x is None:
                    return '\xf5'
                return str(x)
        return hashlib.sha1('\0'.join(map(encode, args))).hexdigest()

    def findbuilderid(buildername):
        bid = bName2bID.get(buildername)
        if bid is None:
            r = migrate_engine.execute(builders.insert(), [{
                'name': buildername,
                'name_hash': hashColumns(buildername),
            }])
            bid = r.inserted_primary_key[0]
            bName2bID[buildername] = bid
        return bid

    c = buildrequests.c
    q = sa.select([c.id, c.buildername])
    for row in migrate_engine.execute(q).fetchall():
        builderid = findbuilderid(row.buildername)
        migrate_engine.execute(
            buildrequests.update(whereclause=(c.id == row.id)),
            builderid=builderid)


def remove_buildername(migrate_engine):

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sautils.Table('builders', metadata, autoload=True)
    sautils.Table('buildsets', metadata, autoload=True)
    buildrequests = sautils.Table('buildrequests', metadata, autoload=True)

    # Specify what the new table should look like
    buildrequests.c.buildername.drop()

    changeset.alter_column(
        sa.Column('builderid', sa.Integer, sa.ForeignKey(
            "builders.id"), nullable=False),
        table=buildrequests,
        metadata=metadata,
        engine=migrate_engine)

    idx = sa.Index('buildrequests_builderid', buildrequests.c.builderid)
    idx.create(migrate_engine)
    idx = sa.Index('buildrequests_buildsetid', buildrequests.c.buildsetid)
    idx.create(migrate_engine)
    idx = sa.Index('buildrequests_complete', buildrequests.c.complete)
    idx.create(migrate_engine)


def upgrade(migrate_engine):
    # add a 'builderid' column to buildrequests
    add_new_schema_parts(migrate_engine)
    # migrate the data to new tables
    migrate_data(migrate_engine)
    # Finally remove the buildername column
    remove_buildername(migrate_engine)

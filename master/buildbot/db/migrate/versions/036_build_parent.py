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

from buildbot.util import sautils


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sautils.Table('builds', metadata, autoload=True)
    buildsets_table = sautils.Table('buildsets', metadata, autoload=True)

    # optional parent build
    parentbuildid = sa.Column('parent_buildid', sa.Integer,
                              sa.ForeignKey('builds.id', use_alter=True, name='parent_buildid'))
    # text describing what is the relationship with the build
    # could be 'triggered from', 'rebuilt from', 'inherited from'
    parent_relationship = sa.Column('parent_relationship', sa.Text)

    parentbuildid.create(buildsets_table)
    parent_relationship.create(buildsets_table)

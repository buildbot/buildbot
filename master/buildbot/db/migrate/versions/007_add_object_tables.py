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

    objects = sautils.Table(
        "objects", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('class_name', sa.String(128), nullable=False),
        sa.UniqueConstraint('name', 'class_name', name='object_identity'),
    )
    objects.create()

    object_state = sautils.Table(
        "object_state", metadata,
        sa.Column("objectid", sa.Integer, sa.ForeignKey('objects.id'),
                  nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("value_json", sa.Text, nullable=False),
        sa.UniqueConstraint('objectid', 'name', name='name_per_object'),
    )
    object_state.create()

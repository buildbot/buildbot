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

from buildbot.db.types.json import JsonObject
from buildbot.util import sautils


def upgrade(migrate_engine):

    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    buildslaves = sautils.Table(
        "buildslaves", metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("info", JsonObject, nullable=False),
    )
    buildslaves.create()

    idx = sa.Index('buildslaves_name', buildslaves.c.name, unique=True)
    idx.create()

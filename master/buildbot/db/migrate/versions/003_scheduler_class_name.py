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

    # add an empty class_name to the schedulers table
    schedulers = sautils.Table('schedulers', metadata, autoload=True)
    class_name = sa.Column('class_name', sa.String(length=128), nullable=False, server_default=sa.DefaultClause(''))
    class_name.create(schedulers, populate_default=True)

    # and an index since we'll be selecting with (name= AND class=)
    idx = sa.Index('name_and_class', schedulers.c.name, schedulers.c.class_name)
    idx.create(migrate_engine)

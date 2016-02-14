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

    steps_table = sautils.Table('steps', metadata, autoload=True)
    builds_table = sautils.Table('builds', metadata, autoload=True)

    # no attempt is made here to move data from one table to the other, since
    # there was no released version of Buildbot with a 'steps' table yet.

    col = sa.Column('state_string', sa.Text, nullable=False, server_default='')
    col.create(steps_table)
    steps_table.c.state_strings_json.drop()

    col = sa.Column('state_string', sa.Text, nullable=False, server_default='')
    col.create(builds_table)
    builds_table.c.state_strings_json.drop()

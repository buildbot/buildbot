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

    sourcestamps_table = sautils.Table('sourcestamps', metadata, autoload=True)
    changes_table = sautils.Table('changes', metadata, autoload=True)

    # Add codebase to tables
    ss_codebase = sa.Column('codebase', sa.String(length=256), nullable=False,
                            server_default=sa.DefaultClause(""))
    ss_codebase.create(sourcestamps_table)

    c_codebase = sa.Column('codebase', sa.String(length=256), nullable=False,
                           server_default=sa.DefaultClause(""))
    c_codebase.create(changes_table)

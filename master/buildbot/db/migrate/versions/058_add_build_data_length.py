# This file is part of Buildbot. Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
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
    # build_data without the 'length' column has never been released, so we don't care about
    # correct values there.
    metadata = sa.MetaData()
    metadata.bind = migrate_engine
    build_data_table = sautils.Table('build_data', metadata, autoload=True)
    length_column = sa.Column('length', sa.Integer, nullable=False, server_default='0')
    length_column.create(build_data_table)

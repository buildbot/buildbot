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

from __future__ import absolute_import
from __future__ import print_function

import sqlalchemy as sa

from buildbot.util import sautils


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine
    # Add buildset_properties.buildsetpropertyid column
    buildset_properties_table = sautils.Table('buildset_properties', metadata, autoload=True)
    buildsetpropertyid = sa.Column('buildsetpropertyid', sa.Integer, nullable=True)
    buildsetpropertyid.create(buildset_properties_table)
    # Add change_properties.changepropertyid column
    change_properties_table = sautils.Table('change_properties', metadata, autoload=True)
    changepropertyid = sa.Column('changepropertyid', sa.Integer, nullable=True)
    changepropertyid.create(change_properties_table)
    # Add build_properties.buildpropertyid column
    build_properties_table = sautils.Table('build_properties', metadata, autoload=True)
    buildpropertyid = sa.Column('buildpropertyid', sa.Integer, nullable=True)
    buildpropertyid.create(build_properties_table)

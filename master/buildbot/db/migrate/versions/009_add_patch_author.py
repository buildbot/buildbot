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

def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    # add an empty class_name to the schedulers table
    patches = sa.Table('patches', metadata, autoload=True)
    patch_author= sa.Column('patch_author', sa.Text, server_default=sa.DefaultClause(''))
    patch_author.create(patches, populate_default=True)
    
    patch_author= sa.Column('patch_comment', sa.Text, server_default=sa.DefaultClause(''))
    patch_author.create(patches, populate_default=True)
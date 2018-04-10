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

from __future__ import absolute_import
from __future__ import print_function
from future.utils import iteritems

import sqlalchemy as sa
from migrate.changeset.constraint import PrimaryKeyConstraint

from buildbot.util import sautils


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    for t, cols in iteritems(TABLES_PKEYS):
        table = sautils.Table(t, metadata, autoload=True)
        pk = PrimaryKeyConstraint(*cols)
        table.append_constraint(pk)
        pk.create()


TABLES_PKEYS = {
    'buildrequest_claims': ['brid'],
    'build_properties': ['buildid', 'name'],
    'logchunks': ['logid', 'first_line', 'last_line'],
    'buildset_properties': ['buildsetid', 'property_name'],
    'change_files': ['changeid', 'filename'],
    'change_properties': ['changeid', 'property_name'],
    'change_users': ['changeid', 'uid'],
    'scheduler_changes': ['schedulerid', 'changeid'],
    'object_state': ['objectid', 'name'],
    'users_info': ['uid', 'attr_type'],
}

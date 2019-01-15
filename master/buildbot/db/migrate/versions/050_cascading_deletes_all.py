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
from migrate.changeset.constraint import ForeignKeyConstraint
from migrate.exceptions import NotSupportedError

from buildbot.util import sautils


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    tables = {}
    for t in TABLES_FKEYS:
        tables[t] = sautils.Table(t, metadata, autoload=True)

    fks_to_change = []
    # We need to parse the reflected model in order to find the automatic
    # fk name that was put.
    # Mysql and postgres have different naming convention so this is not very
    # easy to have generic code working.
    for t, keys in TABLES_FKEYS.items():
        table = tables[t]
        for fk in table.constraints:
            if not isinstance(fk, sa.ForeignKeyConstraint):
                continue
            for c in fk.elements:
                if str(c.column) in keys:
                    # migrate.xx.ForeignKeyConstraint is changing the model
                    # so initializing here would break the iteration
                    # (Set changed size during iteration)
                    fks_to_change.append((
                        table, (fk.columns, [c.column]),
                        dict(name=fk.name, ondelete='CASCADE')))

    for table, args, kwargs in fks_to_change:
        fk = ForeignKeyConstraint(*args, **kwargs)
        table.append_constraint(fk)
        try:
            fk.drop()
        except NotSupportedError:
            # some versions of sqlite do not support drop,
            # but will still update the fk
            pass
        fk.create()


TABLES_FKEYS = {
    'buildrequests': ['buildsets.id', 'builders.id'],
    'buildrequest_claims': ['buildrequests.id', 'masters.id'],
    'build_properties': ['builds.id'],
    'builds': ['builders.id', 'buildrequests.id', 'workers.id', 'masters.id'],
    'steps': ['builds.id'],
    'logs': ['steps.id'],
    'logchunks': ['logs.id'],
    'buildset_properties': ['buildsets.id'],
    'buildsets': ['builds.id'],
    'changesource_masters': ['changesources.id', 'masters.id'],
    # 'configured_workers': ['builder_masters.id', 'workers.id'],
    'connected_workers': ['masters.id', 'workers.id'],
    'changes': ['sourcestamps.id', 'changes.changeid'],
    'change_files': ['changes.changeid'],
    'change_properties': ['changes.changeid'],
    'change_users': ['changes.changeid', 'users.uid'],
    'buildset_sourcestamps': ['buildsets.id', 'sourcestamps.id'],
    'scheduler_masters': ['schedulers.id', 'masters.id'],
    'scheduler_changes': ['schedulers.id', 'changes.changeid'],
    # 'builder_masters': ['builders.id', 'masters.id'],
    'builders_tags': ['builders.id', 'tags.id'],
    'object_state': ['objects.id'],
    'users_info': ['users.uid'],
}

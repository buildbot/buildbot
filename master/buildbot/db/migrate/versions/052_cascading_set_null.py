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

import sqlalchemy as sa
from migrate.changeset.constraint import ForeignKeyConstraint
from migrate.exceptions import NotSupportedError

from buildbot.util import sautils


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    table_names = set(TABLES_FKEYS_SET_NULL.keys())
    table_names.update(TABLES_COLUMNS_NOT_NULL.keys())

    tables = {}
    for t in table_names:
        tables[t] = sautils.Table(t, metadata, autoload=True)

    fks_to_change = []
    # We need to parse the reflected model in order to find the automatic
    # fk name that was put.
    # Mysql and postgres have different naming convention so this is not very
    # easy to have generic code working.
    for t, keys in TABLES_FKEYS_SET_NULL.items():
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
                        dict(name=fk.name, ondelete='SET NULL')))

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

    for t, cols in TABLES_COLUMNS_NOT_NULL.items():
        table = tables[t]
        if table.dialect_options.get('mysql', {}).get('engine') == 'InnoDB':
            migrate_engine.execute('SET FOREIGN_KEY_CHECKS = 0;')
        try:
            for c in table.columns:
                if c.name in cols:
                    c.alter(nullable=False)
        finally:
            if table.dialect_options.get('mysql', {}).get('engine') == 'InnoDB':
                migrate_engine.execute('SET FOREIGN_KEY_CHECKS = 1;')


TABLES_FKEYS_SET_NULL = {
    'builds': ['workers.id'],
    'buildsets': ['parent_buildid'],
    'changes': ['changes.changeid'],
}

TABLES_COLUMNS_NOT_NULL = {
    'buildrequest_claims': ['masterid'],
    'builds': ['builderid'],
    'changes': ['sourcestampid'],
    'logchunks': ['logid'],
    'logs': ['stepid'],
    'scheduler_changes': ['schedulerid', 'changeid'],
    'steps': ['buildid'],
}

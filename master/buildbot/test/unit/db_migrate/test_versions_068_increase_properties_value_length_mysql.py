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

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from twisted.trial import unittest

from buildbot.test.util import migration
from buildbot.util import sautils

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred


# Larger than MySQL TEXT (65535 bytes) so the migration is meaningful on MySQL.
_LARGE_PROPERTY_VALUE = '["' + ('x' * 70000) + '", "test"]'


class Migration(migration.MigrateTestMixin, unittest.TestCase):
    def setUp(self) -> Deferred[None]:  # type: ignore[override]
        return self.setUpMigrateTest()

    def create_tables_thd(self, conn: sa.Connection) -> None:
        metadata = sa.MetaData()

        # Foreign keys are omitted for the purposes of the migration test.
        build_properties = sautils.Table(
            'build_properties',
            metadata,
            sa.Column('buildid', sa.Integer, nullable=False),
            sa.Column('name', sa.String(256), nullable=False),
            sa.Column('value', sa.Text, nullable=False),
            sa.Column('source', sa.String(256), nullable=False),
        )
        build_properties.create(bind=conn)

        buildset_properties = sautils.Table(
            'buildset_properties',
            metadata,
            sa.Column('buildsetid', sa.Integer, nullable=False),
            sa.Column('property_name', sa.String(256), nullable=False),
            sa.Column('property_value', sa.Text, nullable=False),
        )
        buildset_properties.create(bind=conn)

        conn.execute(
            build_properties.insert(),
            [
                {
                    "buildid": 1,
                    "name": "small",
                    "value": '["ok", "test"]',
                    "source": "test",
                }
            ],
        )
        conn.execute(
            buildset_properties.insert(),
            [
                {
                    "buildsetid": 1,
                    "property_name": "small",
                    "property_value": '["ok", "test"]',
                }
            ],
        )
        conn.commit()

    def test_update(self) -> Deferred[None]:
        def setup_thd(conn: sa.Connection) -> None:
            self.create_tables_thd(conn)

        def verify_thd(conn: sa.Connection) -> None:
            metadata = sa.MetaData()
            build_properties = sautils.Table('build_properties', metadata, autoload_with=conn)
            buildset_properties = sautils.Table('buildset_properties', metadata, autoload_with=conn)

            if conn.dialect.name == 'mysql':
                # Confirm MySQL columns were widened past TEXT (64KiB).
                self.assertIn(
                    'longtext',
                    str(build_properties.c.value.type).lower(),
                )
                self.assertIn(
                    'longtext',
                    str(buildset_properties.c.property_value.type).lower(),
                )

            # Existing rows must survive the migration unchanged.
            rows = list(
                conn.execute(
                    sa.select(build_properties.c.name, build_properties.c.value)
                ).fetchall()
            )
            self.assertEqual(rows, [('small', '["ok", "test"]')])

            rows = list(
                conn.execute(
                    sa.select(
                        buildset_properties.c.property_name,
                        buildset_properties.c.property_value,
                    )
                ).fetchall()
            )
            self.assertEqual(rows, [('small', '["ok", "test"]')])

            # Values larger than MySQL TEXT must be storable after the upgrade.
            conn.execute(
                build_properties.insert(),
                [
                    {
                        "buildid": 2,
                        "name": "large",
                        "value": _LARGE_PROPERTY_VALUE,
                        "source": "test",
                    }
                ],
            )
            conn.execute(
                buildset_properties.insert(),
                [
                    {
                        "buildsetid": 2,
                        "property_name": "large",
                        "property_value": _LARGE_PROPERTY_VALUE,
                    }
                ],
            )
            conn.commit()

            value = conn.execute(
                sa.select(build_properties.c.value).where(build_properties.c.name == 'large')
            ).scalar()
            self.assertEqual(value, _LARGE_PROPERTY_VALUE)

            value = conn.execute(
                sa.select(buildset_properties.c.property_value).where(
                    buildset_properties.c.property_name == 'large'
                )
            ).scalar()
            self.assertEqual(value, _LARGE_PROPERTY_VALUE)

        return self.do_test_migration('067', '068', setup_thd, verify_thd)

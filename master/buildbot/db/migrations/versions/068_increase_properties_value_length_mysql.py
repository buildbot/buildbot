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

"""increase build_properties.value and buildset_properties.property_value to LONGTEXT on MySQL

Revision ID: 068
Revises: 067

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = "068"
down_revision = "067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Only MySQL maps sa.Text to a 64KiB TEXT column. Other dialects already
    # accept large property values, so there is nothing to change for them.
    if op.get_bind().dialect.name != "mysql":
        return

    with op.batch_alter_table("build_properties") as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=sa.Text(),
            type_=mysql.LONGTEXT(),
            existing_nullable=False,
            nullable=False,
        )

    with op.batch_alter_table("buildset_properties") as batch_op:
        batch_op.alter_column(
            "property_value",
            existing_type=sa.Text(),
            type_=mysql.LONGTEXT(),
            existing_nullable=False,
            nullable=False,
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "mysql":
        return

    with op.batch_alter_table("build_properties") as batch_op:
        batch_op.alter_column(
            "value",
            existing_type=mysql.LONGTEXT(),
            type_=sa.Text(),
            existing_nullable=False,
            nullable=False,
        )

    with op.batch_alter_table("buildset_properties") as batch_op:
        batch_op.alter_column(
            "property_value",
            existing_type=mysql.LONGTEXT(),
            type_=sa.Text(),
            existing_nullable=False,
            nullable=False,
        )

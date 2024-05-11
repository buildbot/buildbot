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

"""add pause_reason column to workers table

Revision ID: 066
Revises: 065

"""

import sqlalchemy as sa
from alembic import op

from buildbot.util import sautils

# revision identifiers, used by Alembic.
revision = "066"
down_revision = "065"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("builds", sa.Column("locks_duration_s", sa.Integer, nullable=True))

    metadata = sa.MetaData()
    builds_tbl = sautils.Table(
        "builds", metadata, sa.Column("locks_duration_s", sa.Integer, nullable=True)
    )

    op.execute(builds_tbl.update().values({builds_tbl.c.locks_duration_s: 0}))

    with op.batch_alter_table("builds") as batch_op:
        batch_op.alter_column("locks_duration_s", existing_type=sa.Integer, nullable=False)


def downgrade():
    op.drop_column("builds", "locks_duration_s")

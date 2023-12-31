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

"""add locks_acquired_at column to steps table

Revision ID: 063
Revises: 062

"""
import sqlalchemy as sa
from alembic import op

from buildbot.util import sautils

# revision identifiers, used by Alembic.
revision = '063'
down_revision = '062'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("steps", sa.Column("locks_acquired_at", sa.Integer, nullable=True))

    metadata = sa.MetaData()
    steps_tbl = sautils.Table(
        'steps', metadata,
        sa.Column("started_at", sa.Integer),
        sa.Column("locks_acquired_at", sa.Integer)
    )

    op.execute(steps_tbl.update(values={steps_tbl.c.locks_acquired_at: steps_tbl.c.started_at}))


def downgrade():
    op.drop_column("steps", "locks_acquired_at")

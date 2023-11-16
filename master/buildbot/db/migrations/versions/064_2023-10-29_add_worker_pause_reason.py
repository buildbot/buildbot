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

Revision ID: 064
Revises: 063

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '064'
down_revision = '063'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("workers", sa.Column("pause_reason", sa.Text, nullable=True))


def downgrade():
    op.drop_column("workers", "pause_reason")

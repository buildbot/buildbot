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

"""add rebuilt_buildid column to buildsets table

Revision ID: 065
Revises: 064

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '065'
down_revision = '064'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("buildsets") as batch_op:
        batch_op.add_column(
            sa.Column(
                "rebuilt_buildid",
                sa.Integer,
                sa.ForeignKey(
                    "builds.id", use_alter=True, name="rebuilt_buildid", ondelete='SET NULL'
                ),
                nullable=True,
            ),
        )


def downgrade():
    op.drop_column("buildsets", "rebuilt_buildid")

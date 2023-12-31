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

"""add project description format

Revision ID: 062
Revises: 061

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '062'
down_revision = '061'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(
            sa.Column('description_format', sa.Text, nullable=True),
        )
        batch_op.add_column(
            sa.Column('description_html', sa.Text, nullable=True),
        )


def downgrade():
    op.drop_column("projects", "description_format")
    op.drop_column("projects", "description_html")

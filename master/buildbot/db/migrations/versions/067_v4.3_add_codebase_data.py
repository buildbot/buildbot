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

"""add codebases, codebase_commits and codebase_branches tables

Revision ID: 067
Revises: 066

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "067"
down_revision = "066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    hash_length = 40

    op.create_table(
        'codebases',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column(
            'projectid',
            sa.Integer,
            sa.ForeignKey('projects.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('slug', sa.String(50), nullable=False),
        sa.Column('name_hash', sa.String(hash_length), nullable=False),
        mysql_DEFAULT_CHARSET='utf8',
    )

    op.create_table(
        'codebase_commits',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column(
            'codebaseid',
            sa.Integer,
            sa.ForeignKey('codebases.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('author', sa.String(255), nullable=False),
        sa.Column('committer', sa.String(255), nullable=True),
        sa.Column('comments', sa.Text, nullable=False),
        sa.Column('when_timestamp', sa.Integer, nullable=False),
        sa.Column('revision', sa.String(70), nullable=False),
        sa.Column(
            'parent_commitid',
            sa.Integer,
            sa.ForeignKey('codebase_commits.id', ondelete='SET NULL'),
            nullable=True,
        ),
        mysql_DEFAULT_CHARSET='utf8',
    )

    op.create_table(
        'codebase_branches',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column(
            'codebaseid',
            sa.Integer,
            sa.ForeignKey('codebases.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('name_hash', sa.String(hash_length), nullable=False),
        sa.Column(
            'commitid',
            sa.Integer,
            sa.ForeignKey('codebase_commits.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('last_timestamp', sa.Integer, nullable=False),
        mysql_DEFAULT_CHARSET='utf8',
    )

    op.create_index(
        'codebases_projects_name_hash',
        'codebases',
        ['projectid', 'name_hash'],
        unique=True,
    )

    op.create_index(
        'codebase_commits_unique',
        'codebase_commits',
        ['codebaseid', 'revision'],
        unique=True,
    )

    op.create_index(
        'codebase_branches_unique',
        'codebase_branches',
        ['codebaseid', 'name_hash'],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table('codebases')
    op.drop_table('codebase_commits')
    op.drop_table('codebase_branches')
    op.drop_index('codebases_projects_name_hash')
    op.drop_index('codebase_commits_unique')
    op.drop_index('codebase_branches_unique')

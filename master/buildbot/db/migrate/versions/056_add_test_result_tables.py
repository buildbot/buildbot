# This file is part of Buildbot. Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members


import sqlalchemy as sa

from buildbot.util import sautils


def upgrade(migrate_engine):
    metadata = sa.MetaData()
    metadata.bind = migrate_engine

    sautils.Table(
        'builds', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        # ...
    )

    sautils.Table(
        'builders', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        # ...
    )

    sautils.Table(
        'steps', metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        # ...
    )

    test_result_sets = sautils.Table(
        'test_result_sets', metadata,

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('builderid', sa.Integer,
                  sa.ForeignKey('builders.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('buildid', sa.Integer,
                  sa.ForeignKey('builds.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('stepid', sa.Integer,
                  sa.ForeignKey('steps.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('description', sa.Text, nullable=True),

        sa.Column('category', sa.Text, nullable=False),

        sa.Column('value_unit', sa.Text, nullable=False),

        sa.Column('tests_passed', sa.Integer, nullable=True),

        sa.Column('tests_failed', sa.Integer, nullable=True),

        sa.Column('complete', sa.SmallInteger, nullable=False),
    )

    test_results = sautils.Table(
        'test_results', metadata,

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('builderid', sa.Integer,
                  sa.ForeignKey('builders.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('test_result_setid', sa.Integer,
                  sa.ForeignKey('test_result_sets.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('test_nameid', sa.Integer,
                  sa.ForeignKey('test_names.id', ondelete='CASCADE'),
                  nullable=True),

        sa.Column('test_code_pathid', sa.Integer,
                  sa.ForeignKey('test_code_paths.id', ondelete='CASCADE'),
                  nullable=True),

        sa.Column('line', sa.Integer, nullable=True),

        sa.Column('duration_ns', sa.Integer, nullable=True),

        sa.Column('value', sa.Text, nullable=False),
    )

    test_names = sautils.Table(
        'test_names', metadata,

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('builderid', sa.Integer,
                  sa.ForeignKey('builders.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('name', sa.Text, nullable=False),
    )

    test_code_paths = sautils.Table(
        'test_code_paths', metadata,

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('builderid', sa.Integer,
                  sa.ForeignKey('builders.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('path', sa.Text, nullable=False),
    )

    # create the tables
    test_result_sets.create()
    test_names.create()
    test_code_paths.create()
    test_results.create()

    # create indexes
    idx = sa.Index('test_names_name', test_names.c.builderid, test_names.c.name,
                   mysql_length={'name': 255})
    idx.create()

    idx = sa.Index('test_code_paths_path', test_code_paths.c.builderid, test_code_paths.c.path,
                   mysql_length={'path': 255})
    idx.create()

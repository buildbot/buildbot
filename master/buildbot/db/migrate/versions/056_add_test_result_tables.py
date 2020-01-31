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

    steps = sautils.Table(
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

        sa.Column('category', sa.Text, nullable=False),

        sa.Column('value_unit', sa.Text, nullable=False),

        sa.Column('complete', sa.SmallInteger, nullable=False),
    )

    test_result_unparsed_sets = sautils.Table(
        'test_result_unparsed_sets', metadata,

        sa.Column('test_result_setid', sa.Integer,
                  sa.ForeignKey('test_result_sets.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('status', sa.SmallInteger, nullable=False),
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

    test_raw_results = sautils.Table(
        'test_raw_results', metadata,

        sa.Column('id', sa.Integer, primary_key=True),

        sa.Column('test_result_setid', sa.Integer,
                  sa.ForeignKey('test_result_sets.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('type', sa.Text, nullable=False),
    )

    test_raw_result_chunks = sautils.Table(
        'test_raw_result_chunks', metadata,

        sa.Column('test_raw_resultid', sa.Integer,
                  sa.ForeignKey('test_raw_results.id', ondelete='CASCADE'),
                  nullable=False),

        sa.Column('sequence', sa.Integer, nullable=False),

        sa.Column('content', sa.LargeBinary(65536)),

        sa.Column('compressed', sa.SmallInteger, nullable=False),
    )

    # create the tables
    test_result_sets.create()
    test_result_unparsed_sets.create()
    test_names.create()
    test_code_paths.create()
    test_results.create()
    test_raw_results.create()
    test_raw_result_chunks.create()

    # TODO FIXME indexes

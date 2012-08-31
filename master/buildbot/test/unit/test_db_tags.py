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

import mock
import pprint
import sqlalchemy as sa
from twisted.trial import unittest
from twisted.internet import defer, task
from buildbot.db import tags
from buildbot.test.util import connector_component

class TestTagsConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(table_names=[
                     'changes',
                     'tags',
                     'change_tags',
                 ])

        def finish_setup(_):
            self.db.tags = tags.TagsConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # Util methods.

    def populate_test_tags(self, tags_to_insert):
        def thd(conn):
            if tags_to_insert is not None and len(tags_to_insert) > 0:
                conn.execute(self.db.model.tags.insert(), tags_to_insert)
        return self.db.pool.do(thd)

    def populate_test_change_tags(self, tagids_to_insert):
        def thd(conn):
            if tagids_to_insert is not None and len(tagids_to_insert) > 0:
                r = conn.execute(self.db.model.changes.insert(), [dict(
                        author='gkistanova',
                        comments='test',
                        is_dir=0,
                        when_timestamp=266738404,
                    )])

                changeid = r.inserted_primary_key[0]
                change_tags_to_insert = []
                for tagid in tagids_to_insert:
                    change_tags_to_insert.append(dict(changeid=changeid, tagid=tagid))
                conn.execute(self.db.model.change_tags.insert(), change_tags_to_insert)
        return self.db.pool.do(thd)

    def retrieveTags(self, tagids_to_retrieve):
        def thd(conn):
            tags_tbl = self.db.model.tags
            sel = sa.select([tags_tbl.c.id])

            if tagids_to_retrieve is not None and len(tagids_to_retrieve) > 0:
                sel.where(tags_tbl.c.id.in_(tagids_to_retrieve))

            # Request tagids.
            res = conn.execute(sel)
            tagids = [ r.id for r in res ]
            return tagids
        return self.db.pool.do(thd)

    def getTags(self, test_tags):
        tags = []
        if test_tags is not None:
            for t in test_tags:
                tags.append(t['tag'])
        return tags

    def getIds(self, test_tags):
        tagids = []
        if test_tags is not None:
            for t in test_tags:
                tagids.append(t['id'])
        return tagids

    # Data access tests.

    def test_new_tags(self):
        test_tags   = ['tag1', 'tag2', 'tag3' ]
        test_tagids = [ 1, 2, 3 ]

        d = self.populate_test_tags(None)

        def get_rows(_):
            return self.db.tags.resolveTags(test_tags)
        d.addCallback(get_rows)

        def validate_rows(tagids):
            self.assertEqual(tagids, test_tagids)
        d.addCallback(validate_rows)
        return d

    def test_existing_tags(self):
        test_tags = [
                dict(id=10, tag='tag1'),
                dict(id=20, tag='tag2'),
                dict(id=30, tag='tag3'),
            ]
        d = self.populate_test_tags(test_tags)

        def get_rows(_):
            return self.db.tags.resolveTags(self.getTags(test_tags))
        d.addCallback(get_rows)

        def validate_rows(tagids):
            self.assertEqual(tagids, self.getIds(test_tags))
        d.addCallback(validate_rows)
        return d

    def test_mix_new_and_existing_tags(self):
        test_tags = [
                dict(id=10, tag='tag1'),
                dict(id=20, tag='tag2'),
                dict(id=30, tag='tag3'),
            ]
        d = self.populate_test_tags(test_tags)

        # Add a new tag with expected tagid.
        test_tags.append(dict(id=1, tag='tag4'))

        def get_rows(_):
            return self.db.tags.resolveTags(self.getTags(test_tags))
        d.addCallback(get_rows)

        def validate_rows(tagids):
            self.assertEqual(tagids, self.getIds(test_tags))
        d.addCallback(validate_rows)
        return d

    def test_empty_tags(self):
        test_tags = []
        d = self.populate_test_tags(None)

        def get_rows(_):
            return self.db.tags.resolveTags(test_tags)
        d.addCallback(get_rows)

        return self.assertFailure(d, AssertionError)

    def test_none_tags(self):
        test_tags = None
        d = self.populate_test_tags(None)

        def get_rows(_):
            return self.db.tags.resolveTags(test_tags)
        d.addCallback(get_rows)

        return self.assertFailure(d, AssertionError)

    # Note: We never remove tags, so no tests for tags removal.

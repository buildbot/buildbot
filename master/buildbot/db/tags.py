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

"""
Support for tags in the database
"""

import sqlalchemy as sa
from twisted.internet import defer, reactor
from buildbot.db import base

class TagDict(dict):
    pass

class ChangesConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    def resolveTags(self, tags):
        """
        This method adds missing tags to the tags table
        and returns a list of tag ids related to the given
        list of tags. Note that order is not preserved, i.e.
        tagids[0] does not correspond to the tags[0].
        """

        if tags is None:
            return defer.succeed(None)

        def thd(conn):
            assert tags is not None, "tags must be a list, not None"
            transaction = conn.begin()

            tags_tbl = self.db.model.tags

            # Let's check what tags we already have in the database.
            res = conn.execute(
                  sa.select(
                      [tags_tbl.c.tag]
                  ).where(tags_tbl.c.tag.in_(tags)))
            existing_tags = [ r.tag for r in res ]

            tags_to_insert = []
            for tag in tags:
                if tag not in existing_tags:
                    self.check_length(tags_tbl.c.tag, tag)
                    tags_to_insert.append(dict(tag=tag))

            # Insert missing tags if any.
            if tags_to_insert:
                conn.execute(tags_tbl.insert(), tags_to_insert)

            # Request tagids.
            res = conn.execute(
                  sa.select(
                      [tags_tbl.c.id]
                  ).where(tags_tbl.c.tag.in_(tags)))
            tagids = [ r.id for r in res ]

            transaction.commit()
            return tagids

        d = self.db.pool.do(thd)
        return d

    def removeUnusedTags(self, tags):
        """
        Called every time tags consumer record gets deleted, this method
        deletes orphan tags from the tags table.
        """

        if tags is None or len(tags) == 0:
            return defer.succeed(None)

        def thd(conn):
            assert tags is not None and len(tags) > 0
            transaction = conn.begin()
            tags_tbl = self.db.model.tags

            # Select the tagids for the given tags.
            res = conn.execute(
                  sa.select(
                      [tags_tbl.c.id]
                  ).where(tags_tbl.c.tag.in_(tags)))
            tagids_to_delete = [ r.id for r in res ]

            print 'Tagids to delete: %s' % tagids_to_delete

            if len(tagids_to_delete) > 0:
                # We start from the given list and remove from it the tags
                # which are used from somewhere, leaving those safe to delete.
                for table_name in ('change_tags',
                                   # add new relevant table name here.
                                  ):
                    table = self.db.model.metadata.tables[table_name]

                    # Request tagids.
                    res = conn.execute(
                          sa.select(
                              [table.c.tagid]
                          ).where(table.c.tagid.in_(tagids_to_delete)))
                    for r in res:
                        # This tag is still used, keep it
                        tagids_to_delete.remove(r.tagid)

            # Delete all unused tags.
            if len(tagids_to_delete) > 0:
                conn.execute(tags_tbl.delete(
                    tags_tbl.c.id.in_(tagids_to_delete)))

            transaction.commit()
        return self.db.pool.do(thd)

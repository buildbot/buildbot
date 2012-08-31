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

class TagsConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/database.rst

    def resolveTagsSync(self, conn, tags, numTries=3):
        """
        Adds missing tags to the tags table and returns
        a list of tag IDs for the given list of tags.
        Note that order is not preserved, i.e.
        tagids[0] does not correspond to the tags[0].
        This method must be run in a db.pool thread.
        Use resolveTags for deferred.
        """

        assert tags is not None and len(tags) > 0, "tags must be a not empty list"

        # Make sure we have a unique set of tags.
        tags = list(set(tags))

        tags_tbl = self.db.model.tags
        transaction = conn.begin()

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
           try:
               conn.execute(tags_tbl.insert(), tags_to_insert)
           except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
               # It looks like DB Engine does not support transactions.
               transaction.rollback()

               # Try it all over again, in case there was an overlapping,
               # identical call to resolveTagsSync, but retry only
               # requested number of times.
               remainingTries = numTries - 1
               if remainingTries <= 0:
                   raise
               return self.resolveTagsSync(conn, tags, numTries=remainingTries)

        # Request tagids.
        res = conn.execute(
              sa.select(
                  [tags_tbl.c.id]
              ).where(tags_tbl.c.tag.in_(tags)))
        tagids = [ r.id for r in res ]

        transaction.commit()
        return tagids

    def resolveTags(self, tags):
        """
        Deferrs resolveTagsSync to db thread pool and returns a Deferred.
        """
        d = self.db.pool.do(self.resolveTagsSync, tags)
        return d

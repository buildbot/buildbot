# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla-specific Buildbot steps.
#
# The Initial Developer of the Original Code is
# Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Brian Warner <warner@lothar.com>
#   Chris AtLee <catlee@mozilla.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

import cPickle
import textwrap
import os
import sys

from twisted.persisted import styles

from buildbot.db import util
from buildbot.db.schema import base
from buildbot.util import json

# This is version 1, so it introduces a lot of new tables over version 0,
# which had no database.

TABLES = [
    # the schema here is defined as version 1
    textwrap.dedent("""
        CREATE TABLE version (
            version INTEGER NOT NULL -- contains one row, currently set to 1
        );
    """),

    # last_access is used for logging, to record the last time that each
    # client (or rather class of clients) touched the DB. The idea is that if
    # something gets weird, you can check this and discover that you have an
    # older tool (which uses a different schema) mucking things up.
    textwrap.dedent("""
        CREATE TABLE last_access (
            `who` VARCHAR(256) NOT NULL, -- like 'buildbot-0.8.0'
            `writing` INTEGER NOT NULL, -- 1 if you are writing, 0 if you are reading
            -- PRIMARY KEY (who, writing),
            `last_access` TIMESTAMP     -- seconds since epoch
        );
    """),

    textwrap.dedent("""
        CREATE TABLE changes_nextid (next_changeid INTEGER);
    """),

    textwrap.dedent("""
        -- Changes are immutable: once added, never changed
        CREATE TABLE changes (
            `changeid` INTEGER PRIMARY KEY NOT NULL, -- also serves as 'change number'
            `author` VARCHAR(1024) NOT NULL,
            `comments` VARCHAR(1024) NOT NULL, -- too short?
            `is_dir` SMALLINT NOT NULL, -- old, for CVS
            `branch` VARCHAR(1024) NULL,
            `revision` VARCHAR(256), -- CVS uses NULL. too short for darcs?
            `revlink` VARCHAR(256) NULL,
            `when_timestamp` INTEGER NOT NULL, -- copied from incoming Change
            `category` VARCHAR(256) NULL
        );
    """),

    textwrap.dedent("""
        CREATE TABLE change_links (
            `changeid` INTEGER NOT NULL,
            `link` VARCHAR(1024) NOT NULL
        );
    """),

    textwrap.dedent("""
        CREATE TABLE change_files (
            `changeid` INTEGER NOT NULL,
            `filename` VARCHAR(1024) NOT NULL
        );
    """),

    textwrap.dedent("""
        CREATE TABLE change_properties (
            `changeid` INTEGER NOT NULL,
            `property_name` VARCHAR(256) NOT NULL,
            `property_value` VARCHAR(1024) NOT NULL -- too short?
        );
    """),

    # Scheduler tables
    textwrap.dedent("""
        CREATE TABLE schedulers (
            `schedulerid` INTEGER PRIMARY KEY, -- joins to other tables
            `name` VARCHAR(127) UNIQUE NOT NULL,
            `state` VARCHAR(1024) NOT NULL -- JSON-encoded state dictionary
        );
    """),

    textwrap.dedent("""
        CREATE TABLE scheduler_changes (
            `schedulerid` INTEGER,
            `changeid` INTEGER,
            `important` SMALLINT
        );
    """),

    textwrap.dedent("""
        CREATE TABLE scheduler_upstream_buildsets (
            `buildsetid` INTEGER,
            `schedulerid` INTEGER,
            `active` SMALLINT
        );
    """),

    # SourceStamps
    textwrap.dedent("""
        -- SourceStamps are immutable: once added, never changed
        CREATE TABLE sourcestamps (
            `id` INTEGER PRIMARY KEY,
            `branch` VARCHAR(256) default NULL,
            `revision` VARCHAR(256) default NULL,
            `patchid` INTEGER default NULL
        );
    """),
    textwrap.dedent("""
        CREATE TABLE patches (
            `id` INTEGER PRIMARY KEY,
            `patchlevel` INTEGER NOT NULL,
            `patch_base64` TEXT NOT NULL, -- encoded bytestring
            `subdir` TEXT -- usually NULL
        );
    """),
    textwrap.dedent("""
        CREATE TABLE sourcestamp_changes (
            `sourcestampid` INTEGER NOT NULL,
            `changeid` INTEGER NOT NULL
        );
    """),

    # BuildRequests
    textwrap.dedent("""
        -- BuildSets are mutable. Python code may not cache them. Every
        -- BuildRequest must have exactly one associated BuildSet.
        CREATE TABLE buildsets (
            `id` INTEGER PRIMARY KEY NOT NULL,
            `external_idstring` VARCHAR(256),
            `reason` VARCHAR(256),
            `sourcestampid` INTEGER NOT NULL,
            `submitted_at` INTEGER NOT NULL,
            `complete` SMALLINT NOT NULL default 0,
            `complete_at` INTEGER,
            `results` SMALLINT -- 0=SUCCESS,2=FAILURE, from status/builder.py
             -- results is NULL until complete==1
        );
    """),
    textwrap.dedent("""
        CREATE TABLE buildset_properties (
            `buildsetid` INTEGER NOT NULL,
            `property_name` VARCHAR(256) NOT NULL,
            `property_value` VARCHAR(1024) NOT NULL -- too short?
        );
    """),

    textwrap.dedent("""
        -- the buildrequests table represents the queue of builds that need to be
        -- done. In an idle buildbot, all requests will have complete=1.
        -- BuildRequests are mutable. Python code may not cache them.
        CREATE TABLE buildrequests (
            `id` INTEGER PRIMARY KEY NOT NULL,

            -- every BuildRequest has a BuildSet
            -- the sourcestampid and reason live in the BuildSet
            `buildsetid` INTEGER NOT NULL,

            `buildername` VARCHAR(256) NOT NULL,

            `priority` INTEGER NOT NULL default 0,

            -- claimed_at is the time at which a master most recently asserted that
            -- it is responsible for running the build: this will be updated
            -- periodically to maintain the claim
            `claimed_at` INTEGER default 0,

            -- claimed_by indicates which buildmaster has claimed this request. The
            -- 'name' contains hostname/basedir, and will be the same for subsequent
            -- runs of any given buildmaster. The 'incarnation' contains bootime/pid,
            -- and will be different for subsequent runs. This allows each buildmaster
            -- to distinguish their current claims, their old claims, and the claims
            -- of other buildmasters, to treat them each appropriately.
            `claimed_by_name` VARCHAR(256) default NULL,
            `claimed_by_incarnation` VARCHAR(256) default NULL,

            `complete` INTEGER default 0, -- complete=0 means 'pending'

             -- results is only valid when complete==1
            `results` SMALLINT, -- 0=SUCCESS,1=WARNINGS,etc, from status/builder.py

            `submitted_at` INTEGER NOT NULL,

            `complete_at` INTEGER
        );
    """),

    textwrap.dedent("""
        -- this records which builds have been started for each request
        CREATE TABLE builds (
            `id` INTEGER PRIMARY KEY NOT NULL,
            `number` INTEGER NOT NULL, -- BuilderStatus.getBuild(number)
            -- 'number' is scoped to both the local buildmaster and the buildername
            `brid` INTEGER NOT NULL, -- matches buildrequests.id
            `start_time` INTEGER NOT NULL,
            `finish_time` INTEGER
        );
    """),
]

class Upgrader(base.Upgrader):
    def upgrade(self):
        self.test_unicode()
        self.add_tables()
        self.migrate_changes()
        self.set_version()

    def test_unicode(self):
        # first, create a test table
        c = self.conn.cursor()
        c.execute("CREATE TABLE test_unicode (`name` VARCHAR(100))")
        q = util.sql_insert(self.dbapi, 'test_unicode', ["name"])
        try:
            val = u"Frosty the \N{SNOWMAN}"
            c.execute(q, [val])
            c.execute("SELECT * FROM test_unicode")
            row = c.fetchall()[0]
            if row[0] != val:
                raise UnicodeError("Your database doesn't support unicode data; for MySQL, set the default collation to utf8_general_ci.")
        finally:
            pass
            c.execute("DROP TABLE test_unicode")

    def add_tables(self):
        # first, add all of the tables
        c = self.conn.cursor()
        for t in TABLES:
            try:
                c.execute(t)
            except:
                print >>sys.stderr, "error executing SQL query: %s" % t
                raise

    def _addChangeToDatabase(self, change, cursor):
        # strip None from any of these values, just in case
        def remove_none(x):
            if x is None: return u""
            elif isinstance(x, str):
                return x.decode("utf8")
            else:
                return x
        try:
            values = tuple(remove_none(x) for x in
                             (change.number, change.who,
                              change.comments, change.isdir,
                              change.branch, change.revision, change.revlink,
                              change.when, change.category))
        except UnicodeDecodeError, e:
            raise UnicodeError("Trying to import change data as UTF-8 failed.  Please look at contrib/fix_changes_pickle_encoding.py: %s" % str(e))

        q = util.sql_insert(self.dbapi, 'changes',
            """changeid author comments is_dir branch revision
               revlink when_timestamp category""".split())
        cursor.execute(q, values)

        for link in change.links:
            cursor.execute(util.sql_insert(self.dbapi, 'change_links', ('changeid', 'link')),
                          (change.number, link))
        for filename in change.files:
            cursor.execute(util.sql_insert(self.dbapi, 'change_files', ('changeid', 'filename')),
                          (change.number, filename))
        for propname,propvalue in change.properties.properties.items():
            encoded_value = json.dumps(propvalue)
            cursor.execute(util.sql_insert(self.dbapi, 'change_properties',
                                  ('changeid', 'property_name', 'property_value')),
                          (change.number, propname, encoded_value))

    def migrate_changes(self):
        # if we still have a changes.pck, then we need to migrate it
        changes_pickle = os.path.join(self.basedir, "changes.pck")
        if os.path.exists(changes_pickle):
            if not self.quiet: print "migrating changes.pck to database"

            # 'source' will be an old b.c.changes.ChangeMaster instance, with a
            # .changes attribute
            source = cPickle.load(open(changes_pickle,"rb"))
            styles.doUpgrade()

            if not self.quiet: print " (%d Change objects)" % len(source.changes)

            # first, scan for changes without a number.  If we find any, then we'll
            # renumber the changes sequentially
            have_unnumbered = False
            for c in source.changes:
                if c.revision and c.number is None:
                    have_unnumbered = True
                    break
            if have_unnumbered:
                n = 1
                for c in source.changes:
                    if c.revision:
                        c.number = n
                        n = n + 1

            # insert the changes
            cursor = self.conn.cursor()
            for c in source.changes:
                if not c.revision:
                    continue
                self._addChangeToDatabase(c, cursor)

            # update next_changeid
            max_changeid = max([ c.number for c in source.changes if c.revision ] + [ 0 ])
            cursor.execute("""INSERT into changes_nextid VALUES (%d)""" % (max_changeid+1))

            if not self.quiet:
                print "moving changes.pck to changes.pck.old; delete it or keep it as a backup"
            os.rename(changes_pickle, changes_pickle+".old")
        else:
            c = self.conn.cursor()
            c.execute("""INSERT into changes_nextid VALUES (1)""")

    def set_version(self):
        c = self.conn.cursor()
        c.execute("""INSERT INTO version VALUES (1)""")


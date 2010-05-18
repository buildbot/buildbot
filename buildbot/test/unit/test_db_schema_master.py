import os
import threading
import shutil
import cPickle
import pprint

from zope.interface import implements
from twisted.trial import unittest

from buildbot.db.schema import manager
from buildbot.db import dbspec

class Thing(object):
    # simple object-with-attributes for use in faking pickled objects
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class DBSchemaManager(unittest.TestCase):

    def setUp(self):
        self.basedir = "DBSchemaManager"
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        self.spec = dbspec.DBSpec.from_url("sqlite:///state.sqlite", self.basedir)

        self.sm = manager.DBSchemaManager(self.spec, self.basedir)

    ## assertions and utils

    def assertDatabaseOKEmpty(self):
        """
        assert that the database is an upgrade of an empty db
        """
        errs = []
        c = self.spec.get_sync_connection().cursor()

        # check the version
        c.execute("SELECT * FROM version")
        if c.fetchall()[0][0] != self.sm.get_current_version():
            errs.append("VERSION is not up to date")

        # check that the remaining tables are empty
        for empty_tbl in ('changes', 'change_links', 'change_files',
                'change_properties', 'schedulers', 'scheduler_changes',
                'scheduler_upstream_buildsets', 'sourcestamps', 'patches',
                'sourcestamp_changes', 'buildsets', 'buildset_properties',
                'buildrequests', 'builds'):
            c.execute("SELECT * FROM %s" % empty_tbl)
            if len(c.fetchall()) != 0:
                errs.append("table '%s' is not empty" % empty_tbl)

        if errs:
            self.fail("; ".join(errs))

    # populate the basedir with data to test the upgrade process; this should be
    # expanded as more and more data is migrated from the basedir to the database
    def fill_basedir(self):
        self.fill_basedir_changes()

    def fill_basedir_changes(self):
        changes = [
            Thing(number=1, who='dustin', comments='hi, mom', isdir=1,
                branch=None, revision=1233, revlink='http://buildbot.net',
                when=1267419122, category=None, links=[], files=[],
                properties=Thing(properties={})),
            Thing(number=2, who='warner', comments='', isdir=0,
                branch='schedulerdb', revision=1234, revlink='http://pypi.com',
                when=1267419123, category='new', links=[], files=[],
                properties=Thing(properties={})),
            # a change with number=None should cause all changes to be renumbered
            Thing(number=None, who='catlee', comments=None, isdir=0,
                branch=None, revision=1235, revlink=None,
                when=1267419132, category=None, links=[], files=[],
                properties=Thing(properties={'name' : 'jimmy'})),
            # a change with revision=None should be ignored
            Thing(number=6, who='bhearsum', comments='', isdir=0,
                branch='fixes', revision=None, revlink=None,
                when=1267419134, category='nice', links=[], files=[],
                properties=Thing(properties={})),
            Thing(number=7, who='marcusl', comments='', isdir=0,
                branch='jinja', revision=1239, revlink=None,
                when=1267419134, category='cool', links=['http://github.com'],
                files=['main.c', 'util.c', 'ext.c'],
                properties=Thing(properties={
                    'failures' : 3,
                    'tests' : [ 'bogus1', 'bogus2', 'bogus3' ]})),
        ]

        # embed it in a Changes object and pickle it up
        changesource = Thing(changes=changes)
        f = open(os.path.join(self.basedir, "changes.pck"), "w")
        f.write(cPickle.dumps(changesource))

    def assertDatabaseOKFull(self):
        """
        assert that the database is an upgrade of the db created by fill_basedir
        """
        errs = []
        c = self.spec.get_sync_connection().cursor()

        # check the version
        c.execute("SELECT * FROM version")
        if c.fetchall()[0][0] != self.sm.get_current_version():
            errs.append("VERSION is not up to date")

        # do a byte-for-byte comparison of the changes table and friends
        c.execute("""SELECT changeid, author, comments, is_dir, branch, revision,
                    revlink, when_timestamp, category, repository, project
                    FROM changes order by revision""")
        res = list(c.fetchall())
        if res != [
            (1, u'dustin', 'hi, mom', 1, u'', u'1233',
                u'http://buildbot.net', 1267419122, u'', u'', u''),
            (2, u'warner', u'', 0, u'schedulerdb', u'1234',
                u'http://pypi.com', 1267419123, u'new', u'', u''),
            (3, u'catlee', u'', 0, u'', u'1235',
                u'', 1267419132, u'', u'', u''),
            # note change by bhearsum is missing because its revision=None
            (4, u'marcusl', u'', 0, u'jinja', u'1239',
                u'', 1267419134, u'cool', u'', u''),
            ]:
            pprint.pprint(res)
            errs.append("changes table does not match expectations")

        c.execute("""SELECT changeid, link from change_links order by changeid""")
        res = list(c.fetchall())
        if res != [
                (4, u'http://github.com'),
            ]:
            pprint.pprint(res)
            errs.append("change_links table does not match expectations")

        c.execute("""SELECT changeid, filename from change_files order by changeid""")
        res = list(c.fetchall())
        if res != [
                (4, u'main.c'),
                (4, u'util.c'),
                (4, u'ext.c'),
            ]:
            pprint.pprint(res)
            errs.append("change_files table does not match expectations")

        c.execute("""SELECT changeid, property_name, property_value
                    from change_properties order by changeid, property_name""")
        res = list(c.fetchall())
        if res != [
                (3, u'name', u'"jimmy"'),
                (4, u'failures', u'3'),
                (4, u'tests', u'["bogus1", "bogus2", "bogus3"]'),
            ]:
            pprint.pprint(res)
            errs.append("change_properties table does not match expectations")

        # check that the remaining tables are empty
        for empty_tbl in ('schedulers', 'scheduler_changes',
                'scheduler_upstream_buildsets', 'sourcestamps', 'patches',
                'sourcestamp_changes', 'buildsets', 'buildset_properties',
                'buildrequests', 'builds'):
            c.execute("SELECT * FROM %s" % empty_tbl)
            if len(c.fetchall()) != 0:
                errs.append("table '%s' is not empty" % empty_tbl)

        if errs:
            self.fail("; ".join(errs))


    ## tests

    def test_get_current_version(self):
        # this is as much a reminder to write tests for the new version
        # as a test of the (very trivial) method
        self.assertEqual(self.sm.get_current_version(), 5)

    def test_get_db_version_empty(self):
        self.assertEqual(self.sm.get_db_version(), 0)

    def test_get_db_version_int(self):
        conn = self.spec.get_sync_connection()
        c = conn.cursor()
        c.execute("CREATE TABLE version (`version` integer)")
        c.execute("INSERT INTO version values (17)")
        self.assertEqual(self.sm.get_db_version(conn), 17)

    def test_is_current_empty(self):
        self.assertFalse(self.sm.is_current())

    def test_is_current_empty_upgrade(self):
        self.sm.upgrade(quiet=True)
        self.assertTrue(self.sm.is_current())

    def test_upgrade_empty(self):
        self.sm.upgrade(quiet=True)
        self.assertDatabaseOKEmpty()

    def test_upgrade_full(self):
        self.fill_basedir()
        self.sm.upgrade(quiet=True)
        self.assertDatabaseOKFull()

    def test_scheduler_name_uniqueness(self):
        self.sm.upgrade(quiet=True)
        c = self.spec.get_sync_connection().cursor()
        c.execute("""INSERT INTO schedulers (`name`, `class_name`, `state`)
                                             VALUES ('s1', 'Nightly', '')""")
        c.execute("""INSERT INTO schedulers (`name`, `class_name`, `state`)
                                             VALUES ('s1', 'Periodic', '')""")
        self.assertRaises(Exception, c.execute,
                """INSERT INTO schedulers (`name`, `class_name`, `state`)
                                   VALUES ('s1', 'Nightly', '')""")

class MySQLDBSchemaManager(DBSchemaManager):
    def setUp(self):
        self.basedir = "MySQLDBSchemaManager"
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        self.spec = dbspec.DBSpec.from_url("mysql://buildbot_test:buildbot_test@localhost/buildbot_test")

        # Drop all previous tables
        cur = self.spec.get_sync_connection().cursor()
        cur.execute("SHOW TABLES")
        for row in cur.fetchall():
            cur.execute("DROP TABLE %s" % row[0])
        cur.execute("COMMIT")

        self.sm = manager.DBSchemaManager(self.spec, self.basedir)

try:
    import MySQLdb
    conn = MySQLdb.connect(user="buildbot_test", db="buildbot_test", passwd="buildbot_test", use_unicode=True, charset='utf8')
except:
    MySQLDBSchemaManager.skip = True

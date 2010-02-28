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
#   Dustin Mitchell <dustin@zmanda.com>
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

import sys, os, cgi, re

from twisted.python import log, reflect
from twisted.internet import defer, reactor

from buildbot.db.schema.v1 import TABLES
from buildbot.db.connector import DBConnector
from buildbot.db.exceptions import *

class DBSpec(object):
    """
    A specification for the database type and other connection parameters.
    """
    def __init__(self, dbapiName, *connargs, **connkw):
        # special-case 'sqlite3', replacing it with the available implementation
        if dbapiName == 'sqlite3':
            dbapiName = self.get_sqlite_dbapi_name()

        self.dbapiName = dbapiName
        self.connargs = connargs
        self.connkw = connkw

    @classmethod
    def from_url(cls, url, basedir=None):
        """
        Parses a URL of the format
          driver://[username:password@]host:port/database[?args]
        and returns a DB object representing this URL.  Percent-
        substitution will be performed, replacing %(basedir)s with
        the basedir argument.

        raises ValueError on an invalid URL.
        """
        match = re.match(r"""
        ^(?P<driver>\w+)://
        (
            ((?P<user>\w+)(:(?P<passwd>\S+))?@)?
            ((?P<host>[-A-Za-z0-9.]+)(:(?P<port>\d+))?)?/
            (?P<database>\S+?)(\?(?P<args>.*))?
        )?$""", url, re.X)
        if not match:
            raise ValueError("Malformed url")

        d = match.groupdict()
        driver = d['driver']
        user = d['user']
        passwd = d['passwd']
        host = d['host']
        port = d['port']
        if port is not None:
            port = int(port)
        database = d['database']
        args = {}
        if d['args']:
            for key, value in cgi.parse_qsl(d['args']):
                args[key] = value

        if driver == "sqlite":
            # user, passwd, host, and port must all be None
            if not user == passwd == host == port == None:
                raise ValueError("user, passwd, host, port must all be None")
            if not database:
                database = ":memory:"
            else:
                database = database % dict(basedir=basedir)
                database = os.path.join(basedir, database)
            return cls("sqlite3", database, **args)
        elif driver == "mysql":
            args['host'] = host
            args['db'] = database
            if user:
                args['user'] = user
            if passwd:
                args['passwd'] = passwd
            if port:
                args['port'] = port

            return cls("MySQLdb", **args)
        else:
            raise ValueError("Unsupported dbapi %s" % driver)

    def get_sqlite_dbapi_name(self):
        """
        see which dbapi we can use and return that name; prefer
        pysqlite2.dbapi2 if it is available.
        """
        sqlite_dbapi_name = None
        try:
            from pysqlite2 import dbapi2 as sqlite3
            sqlite_dbapi_name = "pysqlite2.dbapi2"
        except ImportError:
            # don't use built-in sqlite3 on 2.5 -- it has *bad* bugs
            if sys.version_info >= (2,6):
                import sqlite3
                sqlite_dbapi_name = "sqlite3"
            else:
                raise
        return sqlite_dbapi_name

    def create_db(self):
        """This is used by the create-master and upgrade-master subcommands, to
        create the database for the very first time. It will refuse to touch an
        existing database, as determined by the presence of a 'version' table."""
        # act just like twisted.enterprise.adbapi, but synchronous
        dbapi = reflect.namedModule(self.dbapiName)

        conn = dbapi.connect(*self.connargs, **self.connkw)
        c = conn.cursor()
        try:
            c.execute("SELECT version FROM version")
            raise DBAlreadyExistsError("Refusing to touch an existing database")
        except (dbapi.OperationalError, dbapi.ProgrammingError):
            # mysql gives _mysql_exceptions.ProgrammingError
            # good, this means the db doesn't exist yet
            pass

        for t in TABLES:
            try:
                c.execute(t)
            except:
                print "error executing SQL: %s" % t
                log.msg("error executing SQL: %s" % t)
                raise
        conn.commit()

    def create_or_upgrade_db(self):
        try:
            # this throws DBAlreadyExistsError for existing databases
            self.create_db()
            # so we'll only get here if create_db() just made the db, in which
            # case it will be up-to-date
            return self.open_db()
        except DBAlreadyExistsError:
            pass
        # so here we've got a pre-existing database, of unknown version
        db = DBConnector(self)
        db.start()
        ver = db.get_version()
        # this will eventually have a structure like follows:
        #if ver == 1:
        #    upgrade_1_to_2(db) # modify tables, update version table to 2
        #    ver = 2
        #if ver == 2:
        #    upgrade_2_to_3(db) # ditto
        #    ver = 3
        #assert ver == 3
        #return db
        assert ver == 1
        # great, we're done!
        return db

    def open_db(self):
        # this will only open a pre-existing database of the current version
        db = DBConnector(self)
        db.start()
        ver = db.get_version()
        if ver is None:
            db.stop()
            raise DatabaseNotReadyError("cannot use empty database")
        if ver != 1:
            db.stop()
            raise DatabaseNotReadyError("db is at version %d, I only know 1" % ver)
        log.msg("using db version %d" % ver)
        return db


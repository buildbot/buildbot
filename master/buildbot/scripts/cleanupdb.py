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

from __future__ import with_statement

import os
import sys
import time

from .upgrade_master import checkBasedir
from .upgrade_master import loadConfig
from buildbot import monkeypatches
from buildbot.db import connector
from buildbot.master import BuildMaster
from buildbot.scripts import base
from buildbot.util import in_reactor
from twisted.internet import defer


@defer.inlineCallbacks
def doCleanupDatabase(config, master_cfg):
    if not config['quiet']:
        print "cleaning database (%s)" % (master_cfg.db['db_url'])

    master = BuildMaster(config['basedir'])
    master.config = master_cfg
    print master.config.logCompressionMethod
    db = connector.DBConnector(master, basedir=config['basedir'])

    yield db.setup(check_version=False, verbose=not config['quiet'])
    res = yield db.logs.getLogs()
    i = 0
    percent = 0
    saved = 0
    for log in res:
        saved += yield db.logs.compressLog(log['id'])
        i += 1
        if not config['quiet'] and percent != i * 100 / len(res):
            percent = i * 100 / len(res)
            print " {}%  {} saved".format(percent, saved)
            saved = 0
            sys.stdout.flush()

    if master_cfg.db['db_url'].startswith("sqlite"):
        if not config['quiet']:
            print "executing sqlite vacuum function..."

        def thd(engine):
            r = engine.execute("vacuum;")
            r.close()
        yield db.pool.do(thd)


@in_reactor
@defer.inlineCallbacks
def cleanupDatabase(config, _noMonkey=False):
    if not _noMonkey:  # pragma: no cover
        monkeypatches.patch_all()

    if not checkBasedir(config):
        defer.returnValue(1)
        return

    os.chdir(config['basedir'])

    try:
        configFile = base.getConfigFileFromTac(config['basedir'])
    except (SyntaxError, ImportError), e:
        print "Unable to load 'buildbot.tac' from '%s':" % config['basedir']
        print e
        defer.returnValue(1)
        return
    master_cfg = loadConfig(config, configFile)
    if not master_cfg:
        defer.returnValue(1)
        return

    yield doCleanupDatabase(config, master_cfg)

    if not config['quiet']:
        print "cleanup complete"

    defer.returnValue(0)

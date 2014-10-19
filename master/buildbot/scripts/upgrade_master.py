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
import traceback

from buildbot import config as config_module
from buildbot import monkeypatches
from buildbot.db import connector
from buildbot.master import BuildMaster
from buildbot.scripts import base
from buildbot.util import in_reactor
from twisted.internet import defer
from twisted.python import runtime
from twisted.python import util


def checkBasedir(config):
    if not config['quiet']:
        print "checking basedir"

    if not base.isBuildmasterDir(config['basedir']):
        return False

    if runtime.platformType != 'win32':  # no pids on win32
        if not config['quiet']:
            print "checking for running master"
        pidfile = os.path.join(config['basedir'], 'twistd.pid')
        if os.path.exists(pidfile):
            print "'%s' exists - is this master still running?" % (pidfile,)
            return False

    tac = base.getConfigFromTac(config['basedir'])
    if tac:
        if isinstance(tac.get('rotateLength', 0), str):
            print "ERROR: rotateLength is a string, it should be a number"
            print "ERROR: Please, edit your buildbot.tac file and run again"
            print "ERROR: See http://trac.buildbot.net/ticket/2588 for more details"
            return False
        if isinstance(tac.get('maxRotatedFiles', 0), str):
            print "ERROR: maxRotatedFiles is a string, it should be a number"
            print "ERROR: Please, edit your buildbot.tac file and run again"
            print "ERROR: See http://trac.buildbot.net/ticket/2588 for more details"
            return False

    return True


def loadConfig(config, configFileName='master.cfg'):
    if not config['quiet']:
        print "checking %s" % configFileName

    try:
        master_cfg = config_module.MasterConfig.loadConfig(
            config['basedir'], configFileName)
    except config_module.ConfigErrors, e:
        print "Errors loading configuration:"
        for msg in e.errors:
            print "  " + msg
        return
    except:
        print "Errors loading configuration:"
        traceback.print_exc(file=sys.stdout)
        return

    return master_cfg


def installFile(config, target, source, overwrite=False):
    with open(source, "rt") as f:
        new_contents = f.read()
    if os.path.exists(target):
        with open(target, "rt") as f:
            old_contents = f.read()
        if old_contents != new_contents:
            if overwrite:
                if not config['quiet']:
                    print "%s has old/modified contents" % target
                    print " overwriting it with new contents"
                with open(target, "wt") as f:
                    f.write(new_contents)
            else:
                if not config['quiet']:
                    print "%s has old/modified contents" % target
                    print " writing new contents to %s.new" % target
                with open(target + ".new", "wt") as f:
                    f.write(new_contents)
        # otherwise, it's up to date
    else:
        if not config['quiet']:
            print "creating %s" % target
        with open(target, "wt") as f:
            f.write(new_contents)


def upgradeFiles(config):
    if not config['quiet']:
        print "upgrading basedir"

    webdir = os.path.join(config['basedir'], "public_html")
    if not os.path.exists(webdir):
        if not config['quiet']:
            print "creating public_html"
        os.mkdir(webdir)

    templdir = os.path.join(config['basedir'], "templates")
    if not os.path.exists(templdir):
        if not config['quiet']:
            print "creating templates"
        os.mkdir(templdir)

    for file in ('bg_gradient.jpg', 'default.css',
                 'robots.txt', 'favicon.ico'):
        source = util.sibpath(__file__, "../status/web/files/%s" % (file,))
        target = os.path.join(webdir, file)
        try:
            installFile(config, target, source)
        except IOError:
            print "Can't write '%s'." % (target,)

    installFile(config, os.path.join(config['basedir'], "master.cfg.sample"),
                util.sibpath(__file__, "sample.cfg"), overwrite=True)

    # if index.html exists, use it to override the root page tempalte
    index_html = os.path.join(webdir, "index.html")
    root_html = os.path.join(templdir, "root.html")
    if os.path.exists(index_html):
        if os.path.exists(root_html):
            print "Notice: %s now overrides %s" % (root_html, index_html)
            print "        as the latter is not used by buildbot anymore."
            print "        Decide which one you want to keep."
        else:
            try:
                print "Notice: Moving %s to %s." % (index_html, root_html)
                print "        You can (and probably want to) remove it if " \
                    "you haven't modified this file."
                os.renames(index_html, root_html)
            except Exception, e:
                print "Error moving %s to %s: %s" % (index_html, root_html,
                                                     str(e))


@defer.inlineCallbacks
def upgradeDatabase(config, master_cfg):
    if not config['quiet']:
        print "upgrading database (%s)" % (master_cfg.db['db_url'])

    master = BuildMaster(config['basedir'])
    master.config = master_cfg
    db = connector.DBConnector(master, basedir=config['basedir'])

    yield db.setup(check_version=False, verbose=not config['quiet'])
    yield db.model.upgrade()


@in_reactor
@defer.inlineCallbacks
def upgradeMaster(config, _noMonkey=False):
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

    upgradeFiles(config)
    yield upgradeDatabase(config, master_cfg)

    if not config['quiet']:
        print "upgrade complete"

    defer.returnValue(0)

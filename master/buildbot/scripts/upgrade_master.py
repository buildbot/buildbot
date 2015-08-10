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
from __future__ import print_function

import os

from buildbot import monkeypatches
from buildbot.db import connector
from buildbot.master import BuildMaster
from buildbot.scripts import base
from buildbot.util import in_reactor
from twisted.internet import defer
from twisted.python import util


def installFile(config, target, source, overwrite=False):
    with open(source, "rt") as f:
        new_contents = f.read()
    if os.path.exists(target):
        with open(target, "rt") as f:
            old_contents = f.read()
        if old_contents != new_contents:
            if overwrite:
                if not config['quiet']:
                    print("%s has old/modified contents" % target)
                    print(" overwriting it with new contents")
                with open(target, "wt") as f:
                    f.write(new_contents)
            else:
                if not config['quiet']:
                    print("%s has old/modified contents" % target)
                    print(" writing new contents to %s.new" % target)
                with open(target + ".new", "wt") as f:
                    f.write(new_contents)
        # otherwise, it's up to date
    else:
        if not config['quiet']:
            print("creating %s" % target)
        with open(target, "wt") as f:
            f.write(new_contents)


def upgradeFiles(config):
    if not config['quiet']:
        print("upgrading basedir")

    webdir = os.path.join(config['basedir'], "public_html")
    if not os.path.exists(webdir):
        if not config['quiet']:
            print("creating public_html")
        os.mkdir(webdir)

    templdir = os.path.join(config['basedir'], "templates")
    if not os.path.exists(templdir):
        if not config['quiet']:
            print("creating templates")
        os.mkdir(templdir)

    installFile(config, os.path.join(config['basedir'], "master.cfg.sample"),
                util.sibpath(__file__, "sample.cfg"), overwrite=True)

    # if index.html exists, use it to override the root page tempalte
    index_html = os.path.join(webdir, "index.html")
    root_html = os.path.join(templdir, "root.html")
    if os.path.exists(index_html):
        if os.path.exists(root_html):
            print("Notice: %s now overrides %s" % (root_html, index_html))
            print("        as the latter is not used by buildbot anymore.")
            print("        Decide which one you want to keep.")
        else:
            try:
                print("Notice: Moving %s to %s." % (index_html, root_html))
                print("        You can (and probably want to) remove it if "
                      "you haven't modified this file.")
                os.renames(index_html, root_html)
            except Exception as e:
                print("Error moving %s to %s: %s" % (index_html, root_html,
                                                     str(e)))


@defer.inlineCallbacks
def upgradeDatabase(config, master_cfg):
    if not config['quiet']:
        print("upgrading database (%s)" % (master_cfg.db['db_url']))

    master = BuildMaster(config['basedir'])
    master.config = master_cfg
    master.db.disownServiceParent()
    db = connector.DBConnector(basedir=config['basedir'])
    db.setServiceParent(master)
    yield db.setup(check_version=False, verbose=not config['quiet'])
    yield db.model.upgrade()
    yield db.masters.setAllMastersActiveLongTimeAgo()


@in_reactor
@defer.inlineCallbacks
def upgradeMaster(config, _noMonkey=False):
    if not _noMonkey:  # pragma: no cover
        monkeypatches.patch_all()

    if not base.checkBasedir(config):
        defer.returnValue(1)
        return

    os.chdir(config['basedir'])

    try:
        configFile = base.getConfigFileFromTac(config['basedir'])
    except (SyntaxError, ImportError) as e:
        print("Unable to load 'buildbot.tac' from '%s':" % config['basedir'])
        print(e)

        defer.returnValue(1)
        return
    master_cfg = base.loadConfig(config, configFile)
    if not master_cfg:
        defer.returnValue(1)
        return

    upgradeFiles(config)
    yield upgradeDatabase(config, master_cfg)

    if not config['quiet']:
        print("upgrade complete")

    defer.returnValue(0)

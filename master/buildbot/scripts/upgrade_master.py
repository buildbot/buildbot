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


import os
import signal
import sys
import traceback

from twisted.internet import defer
from twisted.python import util

from buildbot import monkeypatches
from buildbot.db import connector
from buildbot.master import BuildMaster
from buildbot.scripts import base
from buildbot.util import in_reactor
from buildbot.util import stripUrlPassword


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
    if os.path.exists(webdir):
        print("Notice: public_html is not used starting from Buildbot 0.9.0")
        print("        consider using third party HTTP server for serving "
              "static files")

    installFile(config, os.path.join(config['basedir'], "master.cfg.sample"),
                util.sibpath(__file__, "sample.cfg"), overwrite=True)


@defer.inlineCallbacks
def upgradeDatabase(config, master_cfg):
    if not config['quiet']:
        print("upgrading database (%s)"
              % (stripUrlPassword(master_cfg.db['db_url'])))
        print("Warning: Stopping this process might cause data loss")

    def sighandler(signum, frame):
        msg = " ".join("""
        WARNING: ignoring signal %s.
        This process should not be interrupted to avoid database corruption.
        If you really need to terminate it, use SIGKILL.
        """.split())
        print(msg % signum)

    prev_handlers = {}
    try:
        for signame in ("SIGTERM", "SIGINT", "SIGQUIT", "SIGHUP",
                        "SIGUSR1", "SIGUSR2", "SIGBREAK"):
            if hasattr(signal, signame):
                signum = getattr(signal, signame)
                prev_handlers[signum] = signal.signal(signum, sighandler)

        master = BuildMaster(config['basedir'])
        master.config = master_cfg
        master.db.disownServiceParent()
        db = connector.DBConnector(basedir=config['basedir'])
        db.setServiceParent(master)
        yield db.setup(check_version=False, verbose=not config['quiet'])
        yield db.model.upgrade()
        yield db.masters.setAllMastersActiveLongTimeAgo()

    finally:
        # restore previous signal handlers
        for signum, handler in prev_handlers.items():
            signal.signal(signum, handler)


@in_reactor
def upgradeMaster(config, _noMonkey=False):
    if not _noMonkey:  # pragma: no cover
        monkeypatches.patch_all()

    if not base.checkBasedir(config):
        return defer.succeed(1)

    os.chdir(config['basedir'])

    try:
        configFile = base.getConfigFileFromTac(config['basedir'])
    except (SyntaxError, ImportError):
        print("Unable to load 'buildbot.tac' from '%s':" %
              config['basedir'], file=sys.stderr)
        e = traceback.format_exc()
        print(e, file=sys.stderr)
        return defer.succeed(1)
    master_cfg = base.loadConfig(config, configFile)
    if not master_cfg:
        return defer.succeed(1)
    return _upgradeMaster(config, master_cfg)


@defer.inlineCallbacks
def _upgradeMaster(config, master_cfg):

    try:
        upgradeFiles(config)
        yield upgradeDatabase(config, master_cfg)
    except Exception:
        e = traceback.format_exc()
        print("problem while upgrading!:\n" + e, file=sys.stderr)
        return 1
    else:
        if not config['quiet']:
            print("upgrade complete")

    return 0

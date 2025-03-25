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

from buildbot.db import connector
from buildbot.interfaces import IRenderable
from buildbot.master import BuildMaster
from buildbot.scripts import base
from buildbot.util import in_reactor
from buildbot.util import stripUrlPassword


def installFile(config, target, source, overwrite=False):
    with open(source, encoding='utf-8') as f:
        new_contents = f.read()
    if os.path.exists(target):
        with open(target, encoding='utf-8') as f:
            old_contents = f.read()
        if old_contents != new_contents:
            if overwrite:
                if not config['quiet']:
                    print(f"{target} has old/modified contents")
                    print(" overwriting it with new contents")
                with open(target, "w", encoding='utf-8') as f:
                    f.write(new_contents)
            else:
                if not config['quiet']:
                    print(f"{target} has old/modified contents")
                    print(f" writing new contents to {target}.new")
                with open(target + ".new", "w", encoding='utf-8') as f:
                    f.write(new_contents)
        # otherwise, it's up to date
    else:
        if not config['quiet']:
            print(f"creating {target}")
        with open(target, "w", encoding='utf-8') as f:
            f.write(new_contents)


def upgradeFiles(config):
    if not config['quiet']:
        print("upgrading basedir")

    webdir = os.path.join(config['basedir'], "public_html")
    if os.path.exists(webdir):
        print("Notice: public_html is not used starting from Buildbot 0.9.0")
        print("        consider using third party HTTP server for serving static files")

    installFile(
        config,
        os.path.join(config['basedir'], "master.cfg.sample"),
        util.sibpath(__file__, "sample.cfg"),
        overwrite=True,
    )


@defer.inlineCallbacks
def upgradeDatabase(config, master_cfg):
    if not config['quiet']:
        db_url_cfg = master_cfg.db.db_url
        if IRenderable.providedBy(db_url_cfg):
            # if it's a renderable, assume the password is rendered
            # so no need to try and strip it.
            # Doesn't really make sense for it to be renderable with clear password
            db_url = repr(db_url_cfg)
        else:
            db_url = stripUrlPassword(db_url_cfg)

        print(f"upgrading database ({db_url})")
        print("Warning: Stopping this process might cause data loss")

    def sighandler(signum, frame):
        msg = " ".join(
            """
        WARNING: ignoring signal {}.
        This process should not be interrupted to avoid database corruption.
        If you really need to terminate it, use SIGKILL.
        """.split()
        )
        print(msg.format(signum))

    prev_handlers = {}
    db = None

    try:
        for signame in ("SIGTERM", "SIGINT", "SIGQUIT", "SIGHUP", "SIGUSR1", "SIGUSR2", "SIGBREAK"):
            if hasattr(signal, signame):
                signum = getattr(signal, signame)
                prev_handlers[signum] = signal.signal(signum, sighandler)

        master = BuildMaster(config['basedir'])
        master.config = master_cfg
        db = connector.DBConnector(basedir=config['basedir'])
        yield db.set_master(master)
        yield master.secrets_manager.setup()
        yield db.setup(check_version=False, verbose=not config['quiet'])
        yield db.model.upgrade()
        yield db.masters.setAllMastersActiveLongTimeAgo()

    finally:
        # restore previous signal handlers
        for signum, handler in prev_handlers.items():
            signal.signal(signum, handler)

        if db is not None and db.pool is not None:
            yield db.pool.stop()


@in_reactor
def upgradeMaster(config):
    if not base.checkBasedir(config):
        return defer.succeed(1)

    orig_cwd = os.getcwd()

    try:
        os.chdir(config['basedir'])

        try:
            configFile = base.getConfigFileFromTac(config['basedir'])
        except (SyntaxError, ImportError):
            print(f"Unable to load 'buildbot.tac' from '{config['basedir']}':", file=sys.stderr)
            e = traceback.format_exc()
            print(e, file=sys.stderr)
            return defer.succeed(1)
        master_cfg = base.loadConfig(config, configFile)
        if not master_cfg:
            return defer.succeed(1)
        return _upgradeMaster(config, master_cfg)

    finally:
        os.chdir(orig_cwd)


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

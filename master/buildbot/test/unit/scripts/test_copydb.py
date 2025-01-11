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

from __future__ import annotations

import os
import platform
import textwrap
from typing import Any

from twisted.trial import unittest

from buildbot.config import BuilderConfig
from buildbot.db import enginestrategy
from buildbot.plugins import schedulers
from buildbot.process.factory import BuildFactory
from buildbot.scripts import copydb
from buildbot.steps.master import MasterShellCommand
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import db
from buildbot.test.util import dirs
from buildbot.test.util import misc
from buildbot.test.util.integration import RunMasterBase
from buildbot.util.twisted import async_to_deferred


def get_script_config(destination_url: str = 'sqlite://', **kwargs: object) -> dict[str, Any]:
    config = {
        "quiet": False,
        "basedir": os.path.abspath('basedir'),
        'destination_url': destination_url,
        'ignore-fk-error-rows': True,
    }
    config.update(kwargs)
    return config


def write_buildbot_tac(path: str) -> None:
    with open(path, "w", encoding='utf-8') as f:
        f.write(
            textwrap.dedent("""
            from twisted.application import service
            application = service.Application('buildmaster')
        """)
        )


class TestCopyDb(misc.StdoutAssertionsMixin, dirs.DirsMixin, TestReactorMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.setup_test_reactor()
        self.setUpDirs('basedir')
        write_buildbot_tac(os.path.join('basedir', 'buildbot.tac'))
        self.setUpStdoutAssertions()

    def create_master_cfg(self, db_url: str = 'sqlite://', extraconfig: str = "") -> None:
        with open(os.path.join('basedir', 'master.cfg'), "w", encoding='utf-8') as f:
            f.write(
                textwrap.dedent(f"""
                from buildbot.plugins import *
                c = BuildmasterConfig = dict()
                c['db_url'] = {db_url!r}
                c['buildbotNetUsageData'] = None
                c['multiMaster'] = True  # don't complain for no builders
                {extraconfig}
            """)
            )

    @async_to_deferred
    async def test_not_basedir(self) -> None:
        res = await copydb._copy_database_in_reactor(get_script_config(basedir='doesntexist'))
        self.assertEqual(res, 1)
        tac_path = os.path.join('doesntexist', 'buildbot.tac')
        self.assertInStdout(f'error reading \'{tac_path}\': No such file or directory')

    @async_to_deferred
    async def test_bad_config(self) -> None:
        res = await copydb._copy_database_in_reactor(get_script_config(basedir='basedir'))
        self.assertEqual(res, 1)
        master_cfg_path = os.path.abspath(os.path.join('basedir', 'master.cfg'))
        self.assertInStdout(f'configuration file \'{master_cfg_path}\' does not exist')

    @async_to_deferred
    async def test_bad_config2(self) -> None:
        self.create_master_cfg(extraconfig="++++ # syntaxerror")
        res = await copydb._copy_database_in_reactor(get_script_config(basedir='basedir'))
        self.assertEqual(res, 1)
        self.assertInStdout("encountered a SyntaxError while parsing config file:")
        # config logs an error via log.err, we must eat it or trial will
        # complain
        self.flushLoggedErrors()


class TestCopyDbRealDb(misc.StdoutAssertionsMixin, RunMasterBase, dirs.DirsMixin, TestReactorMixin):
    INITIAL_DB_URL = 'sqlite:///tmp.sqlite'

    def setUp(self) -> None:
        self.setUpDirs('basedir')
        self.setUpStdoutAssertions()  # comment out to see stdout from script
        write_buildbot_tac(os.path.join('basedir', 'buildbot.tac'))

    async def create_master_config(self) -> int:
        f = BuildFactory()
        cmd = "dir" if platform.system() in ("Windows", "Microsoft") else "ls"
        f.addStep(MasterShellCommand(cmd))

        config_dict = {
            'builders': [
                BuilderConfig(
                    name="testy",
                    workernames=["local1"],
                    factory=f,
                ),
            ],
            'schedulers': [schedulers.ForceScheduler(name="force", builderNames=["testy"])],
            # Disable checks about missing scheduler.
            'multiMaster': True,
            'db_url': self.INITIAL_DB_URL,
        }
        await self.setup_master(config_dict, basedir='basedir')
        builder_id = await self.master.data.updates.findBuilderId('testy')

        return builder_id

    def create_master_config_file(self, db_url: str) -> None:
        with open(os.path.join('basedir', 'master.cfg'), "w", encoding='utf-8') as f:
            f.write(
                textwrap.dedent(f"""
                from buildbot.plugins import *
                c = BuildmasterConfig = dict()
                c['db_url'] = {db_url!r}
                c['buildbotNetUsageData'] = None
                c['multiMaster'] = True  # don't complain for no builders
            """)
            )

    def resolve_db_url(self) -> str:
        # test may use mysql or pg if configured in env
        envkey = "BUILDBOT_TEST_DB_URL"
        if envkey not in os.environ or os.environ[envkey] == 'sqlite://':
            return "sqlite:///" + os.path.abspath(os.path.join("basedir", "dest.sqlite"))
        return os.environ[envkey]

    def drop_database_tables(self, db_url: str) -> None:
        engine = enginestrategy.create_engine(db_url, basedir='basedir')
        with engine.connect() as conn:
            db.thd_clean_database(conn)
        engine.dispose()

    @async_to_deferred
    async def test_full(self) -> None:
        await self.create_master_config()

        await self.doForceBuild()
        await self.doForceBuild()
        await self.doForceBuild()

        await self.tested_master.shutdown()

        self.create_master_config_file(self.INITIAL_DB_URL)

        dest_db_url = db.resolve_test_index_in_db_url(self.resolve_db_url())

        self.drop_database_tables(dest_db_url)
        self.addCleanup(lambda: self.drop_database_tables(dest_db_url))

        script_config = get_script_config(destination_url=dest_db_url)
        res = await copydb._copy_database_in_reactor(script_config)
        self.assertEqual(res, 0)

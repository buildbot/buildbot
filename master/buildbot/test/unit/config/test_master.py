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

import builtins
import os
import re
import textwrap
from importlib.util import find_spec
from typing import TYPE_CHECKING
from typing import Any
from unittest import mock

from parameterized import parameterized
from twisted.internet import defer
from twisted.trial import unittest
from zope.interface import implementer

from buildbot import config
from buildbot import configurators
from buildbot import interfaces
from buildbot import locks
from buildbot import revlinks
from buildbot import worker
from buildbot.changes import base as changes_base
from buildbot.config.errors import capture_config_errors
from buildbot.config.master import FileLoader
from buildbot.config.master import loadConfigDict
from buildbot.process import factory
from buildbot.process import properties
from buildbot.process.codebase import Codebase
from buildbot.process.project import Project
from buildbot.schedulers import base as schedulers_base
from buildbot.test.util import dirs
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.util import service
from buildbot.warnings import ConfigWarning
from buildbot.warnings import DeprecatedApiWarning

if TYPE_CHECKING:
    from buildbot.config.master import MasterConfig
    from buildbot.util.twisted import InlineCallbacksType

HAS_ZSTD = find_spec('zstandard') is not None

global_defaults = {
    "title": 'Buildbot',
    "titleURL": 'http://buildbot.net/',
    "buildbotURL": 'http://localhost:8080/',
    "logCompressionLimit": 4096,
    "logCompressionMethod": 'zstd' if HAS_ZSTD else 'gz',
    "logEncoding": 'utf-8',
    "logMaxTailSize": None,
    "logMaxSize": None,
    "properties": properties.Properties(),
    "collapseRequests": None,
    "prioritizeBuilders": None,
    "select_next_worker": None,
    "protocols": {},
    "multiMaster": False,
    "manhole": None,
    # in unit tests we default to None, but normally defaults to 'basic'
    "buildbotNetUsageData": None,
    "www": {
        "port": None,
        "plugins": {},
        "auth": {'name': 'NoAuth'},
        "authz": {},
        "avatar_methods": {'name': 'gravatar'},
        "logfileName": 'http.log',
    },
}


class FakeChangeSource(changes_base.ChangeSource):
    def __init__(self) -> None:
        super().__init__(name='FakeChangeSource')


@implementer(interfaces.IScheduler)
class FakeScheduler:
    def __init__(self, name: str) -> None:
        self.name = name


class FakeBuilder:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


@implementer(interfaces.IWorker)
class FakeWorker:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    @property
    def workername(self) -> str:
        return self.name  # type: ignore[attr-defined]


@implementer(interfaces.IMachine)
class FakeMachine:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class ConfigLoaderTests(ConfigErrorsMixin, dirs.DirsMixin, unittest.SynchronousTestCase):
    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.basedir = os.path.abspath('basedir')
        self.filename = os.path.join(self.basedir, 'test.cfg')
        self.patch(config.master, "get_is_in_unit_tests", lambda: False)

        return self.setUpDirs('basedir')

    def install_config_file(
        self, config_file: str, other_files: dict[str, str] | None = None
    ) -> None:
        if other_files is None:
            other_files = {}
        config_file = textwrap.dedent(config_file)
        with open(os.path.join(self.basedir, self.filename), "w", encoding='utf-8') as f:
            f.write(config_file)
        for file, contents in other_files.items():
            with open(file, "w", encoding='utf-8') as f:
                f.write(contents)

    def test_loadConfig_missing_file(self) -> None:
        with self.assertRaisesConfigError(re.compile("configuration file .* does not exist")):
            loadConfigDict(self.basedir, self.filename)

    def test_loadConfig_missing_basedir(self) -> None:
        with self.assertRaisesConfigError(re.compile("basedir .* does not exist")):
            loadConfigDict(os.path.join(self.basedir, 'NO'), 'test.cfg')

    def test_loadConfig_open_error(self) -> None:
        """
        Check that loadConfig() raises correct ConfigError exception in cases
        when configure file is found, but we fail to open it.
        """

        def raise_IOError(*args: Any, **kwargs: Any) -> None:
            raise OSError("error_msg")

        self.install_config_file('#dummy')

        # override build-in open() function to always rise IOError
        self.patch(builtins, "open", raise_IOError)

        # check that we got the expected ConfigError exception
        with self.assertRaisesConfigError(
            re.compile("unable to open configuration file .*: error_msg")
        ):
            loadConfigDict(self.basedir, self.filename)

    def test_loadConfig_parse_error(self) -> None:
        self.install_config_file('def x:\nbar')
        with self.assertRaisesConfigError(
            re.compile("encountered a SyntaxError while parsing config file:")
        ):
            loadConfigDict(self.basedir, self.filename)

    def test_loadConfig_eval_ConfigError(self) -> None:
        self.install_config_file("""\
                from buildbot import config
                BuildmasterConfig = { 'multiMaster': True }
                config.error('oh noes!')""")
        with self.assertRaisesConfigError("oh noes"):
            loadConfigDict(self.basedir, self.filename)

    def test_loadConfig_eval_otherError(self) -> None:
        self.install_config_file("""\
                from buildbot import config
                BuildmasterConfig = { 'multiMaster': True }
                raise ValueError('oh noes')""")
        with self.assertRaisesConfigError(
            "error while parsing config file: oh noes (traceback in logfile)"
        ):
            loadConfigDict(self.basedir, self.filename)

        [error] = self.flushLoggedErrors(ValueError)
        self.assertEqual(error.value.args, ("oh noes",))

    def test_loadConfig_no_BuildmasterConfig(self) -> None:
        self.install_config_file('x=10')
        with self.assertRaisesConfigError("does not define 'BuildmasterConfig'"):
            loadConfigDict(self.basedir, self.filename)

    def test_loadConfig_with_local_import(self) -> None:
        self.install_config_file(
            """\
                from subsidiary_module import x
                BuildmasterConfig = dict(x=x)
                """,
            {'basedir/subsidiary_module.py': "x = 10"},
        )
        _, rv = loadConfigDict(self.basedir, self.filename)
        self.assertEqual(rv, {'x': 10})


class MasterConfigTests(ConfigErrorsMixin, dirs.DirsMixin, unittest.TestCase):
    maxDiff = None

    def setUp(self) -> defer.Deferred[None]:  # type: ignore[override]
        self.basedir = os.path.abspath('basedir')
        self.filename = os.path.join(self.basedir, 'test.cfg')
        return self.setUpDirs('basedir')

    # utils

    def patch_load_helpers(self) -> None:
        # patch out all of the "helpers" for loadConfig with null functions
        for n in dir(config.master.MasterConfig):
            if n.startswith('load_'):
                typ = 'loader'
            elif n.startswith('check_'):
                typ = 'checker'
            else:
                continue

            v = getattr(config.master.MasterConfig, n)
            if callable(v):
                if typ == 'loader':
                    self.patch(
                        config.master.MasterConfig,
                        n,
                        mock.Mock(side_effect=lambda filename, config_dict: None),
                    )
                else:
                    self.patch(config.master.MasterConfig, n, mock.Mock(side_effect=lambda: None))

    def install_config_file(
        self, config_file: str, other_files: dict[str, str] | None = None
    ) -> None:
        if other_files is None:
            other_files = {}
        config_file = textwrap.dedent(config_file)
        with open(os.path.join(self.basedir, self.filename), "w", encoding='utf-8') as f:
            f.write(config_file)
        for file, contents in other_files.items():
            with open(file, "w", encoding='utf-8') as f:
                f.write(contents)

    # tests

    def test_defaults(self) -> None:
        cfg = config.master.MasterConfig()
        expected = {
            # validation,
            "db": config.master.DBConfig(db_url='sqlite:///state.sqlite'),
            "mq": {"type": 'simple'},
            "metrics": None,
            "caches": {"Changes": 10, "Builds": 15},
            "schedulers": {},
            "builders": [],
            "workers": [],
            "change_sources": [],
            "status": [],
            "user_managers": [],
            "revlink": revlinks.default_revlink_matcher,
        }
        expected.update(global_defaults)
        expected['buildbotNetUsageData'] = 'basic'
        got = {attr: getattr(cfg, attr) for attr, exp in expected.items()}
        got = interfaces.IConfigured(got).getConfigDict()
        expected = interfaces.IConfigured(expected).getConfigDict()
        self.assertEqual(got, expected)

    def test_defaults_validation(self) -> None:
        # re's aren't comparable, but we can make sure the keys match
        cfg = config.master.MasterConfig()
        self.assertEqual(
            sorted(cfg.validation.keys()),
            sorted([
                'branch',
                'revision',
                'property_name',
                'property_value',
            ]),
        )

    def test_loadConfig_eval_ConfigErrors(self) -> None:
        # We test a config that has embedded errors, as well
        # as semantic errors that get added later. If an exception is raised
        # prematurely, then the semantic errors wouldn't get reported.
        self.install_config_file("""\
                from buildbot import config
                BuildmasterConfig = {}
                config.error('oh noes!')
                config.error('noes too!')""")

        with capture_config_errors() as errors:
            FileLoader(self.basedir, self.filename).loadConfig()

        self.assertEqual(
            errors.errors,
            ['oh noes!', 'noes too!', 'no workers are configured', 'no builders are configured'],
        )

    def test_loadConfig_unknown_key(self) -> None:
        self.patch_load_helpers()
        self.install_config_file("""\
                BuildmasterConfig = dict(foo=10)
                """)
        with self.assertRaisesConfigError("Unknown BuildmasterConfig key foo"):
            FileLoader(self.basedir, self.filename).loadConfig()

    def test_loadConfig_unknown_keys(self) -> None:
        self.patch_load_helpers()
        self.install_config_file("""\
                BuildmasterConfig = dict(foo=10, bar=20)
                """)
        with self.assertRaisesConfigError("Unknown BuildmasterConfig keys bar, foo"):
            FileLoader(self.basedir, self.filename).loadConfig()

    def test_loadConfig_success(self) -> None:
        self.patch_load_helpers()
        self.install_config_file("""\
                BuildmasterConfig = dict()
                """)
        rv = FileLoader(self.basedir, self.filename).loadConfig()
        self.assertIsInstance(rv, config.master.MasterConfig)

        # make sure all of the loaders and checkers are called
        self.assertTrue(rv.load_global.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.load_validation.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.load_dbconfig.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.load_metrics.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.load_caches.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.load_schedulers.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.load_builders.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.load_workers.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.load_change_sources.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.load_machines.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.load_user_managers.called)  # type: ignore[attr-defined]

        self.assertTrue(rv.check_single_master.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.check_schedulers.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.check_locks.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.check_builders.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.check_ports.called)  # type: ignore[attr-defined]
        self.assertTrue(rv.check_machines.called)  # type: ignore[attr-defined]

    def test_preChangeGenerator(self) -> None:
        cfg = config.master.MasterConfig()
        self.assertEqual(
            {
                'author': None,
                'files': None,
                'comments': None,
                'revision': None,
                'when_timestamp': None,
                'branch': None,
                'category': None,
                'revlink': '',
                'properties': {},
                'repository': '',
                'project': '',
                'codebase': None,
            },
            cfg.preChangeGenerator(),
        )


class MasterConfig_loaders(ConfigErrorsMixin, unittest.TestCase):
    filename = 'test.cfg'

    def setUp(self) -> None:
        self.cfg = config.master.MasterConfig()

    # utils

    def assertResults(self, **expected: object) -> None:
        got = {attr: getattr(self.cfg, attr) for attr, exp in expected.items()}
        got = interfaces.IConfigured(got).getConfigDict()
        expected = interfaces.IConfigured(expected).getConfigDict()

        self.assertEqual(got, expected)

    # tests

    def test_load_global_defaults(self) -> None:
        self.maxDiff = None
        self.cfg.load_global(self.filename, {})
        self.assertResults(**global_defaults)

    def test_load_global_string_param_not_string(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_global(self.filename, {"title": 10})
        self.assertConfigError(errors, 'must be a string')

    def test_load_global_int_param_not_int(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_global(self.filename, {'changeHorizon': 'yes'})

        self.assertConfigError(errors, 'must be an int')

    def test_load_global_protocols_not_dict(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_global(self.filename, {'protocols': "test"})
        self.assertConfigError(errors, "c['protocols'] must be dict")

    def test_load_global_protocols_key_int(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_global(self.filename, {'protocols': {321: {"port": 123}}})

        self.assertConfigError(errors, "c['protocols'] keys must be strings")

    def test_load_global_protocols_value_not_dict(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_global(self.filename, {'protocols': {"pb": 123}})

        self.assertConfigError(errors, "c['protocols']['pb'] must be a dict")

    def do_test_load_global(self, config_dict: dict[str, Any], **expected: Any) -> None:
        self.cfg.load_global(self.filename, config_dict)
        self.assertResults(**expected)

    def test_load_global_title(self) -> None:
        self.do_test_load_global({"title": 'hi'}, title='hi')

    def test_load_global_title_too_long(self) -> None:
        with assertProducesWarning(ConfigWarning, message_pattern=r"Title is too long"):
            self.do_test_load_global({"title": "Very very very very very long title"})

    def test_load_global_titleURL(self) -> None:
        self.do_test_load_global({"titleURL": 'hi'}, titleURL='hi/')

    def test_load_global_buildbotURL(self) -> None:
        self.do_test_load_global({"buildbotURL": 'hey'}, buildbotURL='hey/')

    def test_load_global_changeHorizon(self) -> None:
        self.do_test_load_global({"changeHorizon": 10}, changeHorizon=10)

    def test_load_global_changeHorizon_none(self) -> None:
        self.do_test_load_global({"changeHorizo": None}, changeHorizon=None)

    def test_load_global_buildbotNetUsageData(self) -> None:
        self.patch(config.master, "get_is_in_unit_tests", lambda: False)
        with assertProducesWarning(
            ConfigWarning,
            message_pattern=r"`buildbotNetUsageData` is not configured and defaults to basic.",
        ):
            self.do_test_load_global({})

    def test_load_global_logCompressionLimit(self) -> None:
        self.do_test_load_global({"logCompressionLimit": 10}, logCompressionLimit=10)

    def test_load_global_logCompressionMethod(self) -> None:
        self.do_test_load_global({"logCompressionMethod": 'bz2'}, logCompressionMethod='bz2')

    def test_load_global_logCompressionMethod_invalid(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_global(self.filename, {'logCompressionMethod': 'foo'})

        self.assertConfigError(
            errors, "c['logCompressionMethod'] must be 'raw', 'bz2', 'gz', 'lz4', 'br' or 'zstd'"
        )

    def test_load_global_codebaseGenerator(self) -> None:
        func = lambda _: "dummy"
        self.do_test_load_global({"codebaseGenerator": func}, codebaseGenerator=func)

    def test_load_global_codebaseGenerator_invalid(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_global(self.filename, {'codebaseGenerator': 'dummy'})

        self.assertConfigError(
            errors, "codebaseGenerator must be a callable accepting a dict and returning a str"
        )

    def test_load_global_logMaxSize(self) -> None:
        self.do_test_load_global({"logMaxSize": 123}, logMaxSize=123)

    def test_load_global_logMaxTailSize(self) -> None:
        self.do_test_load_global({"logMaxTailSize": 123}, logMaxTailSize=123)

    def test_load_global_logEncoding(self) -> None:
        self.do_test_load_global({"logEncoding": 'latin-2'}, logEncoding='latin-2')

    def test_load_global_properties(self) -> None:
        exp = properties.Properties()
        exp.setProperty('x', 10, self.filename)
        self.do_test_load_global({"properties": {"x": 10}}, properties=exp)

    def test_load_global_properties_invalid(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_global(self.filename, {'properties': 'yes'})

        self.assertConfigError(errors, "must be a dictionary")

    def test_load_global_collapseRequests_bool(self) -> None:
        self.do_test_load_global({"collapseRequests": False}, collapseRequests=False)

    def test_load_global_collapseRequests_callable(self) -> None:
        callable = lambda: None
        self.do_test_load_global({"collapseRequests": callable}, collapseRequests=callable)

    def test_load_global_collapseRequests_invalid(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_global(self.filename, {'collapseRequests': 'yes'})

        self.assertConfigError(errors, "must be a callable, True, or False")

    def test_load_global_prioritizeBuilders_callable(self) -> None:
        callable = lambda: None
        self.do_test_load_global({"prioritizeBuilders": callable}, prioritizeBuilders=callable)

    def test_load_global_prioritizeBuilders_invalid(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_global(self.filename, {'prioritizeBuilders': 'yes'})

        self.assertConfigError(errors, "must be a callable")

    def test_load_global_select_next_worker_callable(self) -> None:
        callable = lambda: None
        self.do_test_load_global({"select_next_worker": callable}, select_next_worker=callable)

    def test_load_global_select_next_worker_invalid(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_global(self.filename, {"select_next_worker": "yes"})

        self.assertConfigError(errors, "must be a callable")

    def test_load_global_protocols_str(self) -> None:
        self.do_test_load_global(
            {"protocols": {'pb': {'port': 'udp:123'}}}, protocols={'pb': {'port': 'udp:123'}}
        )

    def test_load_global_multiMaster(self) -> None:
        self.do_test_load_global({"multiMaster": 1}, multiMaster=1)

    def test_load_global_manhole(self) -> None:
        mh = mock.Mock(name='manhole')
        self.do_test_load_global({"manhole": mh}, manhole=mh)

    def test_load_global_revlink_callable(self) -> None:
        callable = lambda: None
        self.do_test_load_global({"revlink": callable}, revlink=callable)

    def test_load_global_revlink_invalid(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_global(self.filename, {'revlink': ''})

        self.assertConfigError(errors, "must be a callable")

    def test_load_validation_defaults(self) -> None:
        self.cfg.load_validation(self.filename, {})
        self.assertEqual(
            sorted(self.cfg.validation.keys()),
            sorted([
                'branch',
                'revision',
                'property_name',
                'property_value',
            ]),
        )

    def test_load_validation_invalid(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_validation(self.filename, {'validation': 'plz'})

        self.assertConfigError(errors, "must be a dictionary")

    def test_load_validation_unk_keys(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_validation(self.filename, {'validation': {'users': '.*'}})

        self.assertConfigError(errors, "unrecognized validation key(s)")

    def test_load_validation(self) -> None:
        r = re.compile('.*')
        self.cfg.load_validation(self.filename, {"validation": {"branch": r}})
        self.assertEqual(self.cfg.validation['branch'], r)
        # check that defaults are still around
        self.assertIn('revision', self.cfg.validation)

    def test_load_db_defaults(self) -> None:
        self.cfg.load_dbconfig(self.filename, {})
        self.assertResults(
            db=config.master.DBConfig(db_url='sqlite:///state.sqlite', engine_kwargs={})
        )

    def test_load_db_db_url(self) -> None:
        self.cfg.load_dbconfig(self.filename, {"db_url": 'abcd'})
        self.assertResults(db=config.master.DBConfig(db_url='abcd'))

    def test_load_db_dict(self) -> None:
        self.cfg.load_dbconfig(self.filename, {'db': {'db_url': 'abcd'}})
        self.assertResults(db=config.master.DBConfig(db_url='abcd'))

    def test_load_db_dict_renderable_url(self) -> None:
        self.cfg.load_dbconfig(self.filename, {'db': {'db_url': properties.Interpolate('abcd')}})
        self.assertResults(db=config.master.DBConfig(db_url='abcd'))

    def test_load_db_unk_keys(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_dbconfig(self.filename, {'db': {'db_url': 'abcd', 'bar': 'bar'}})

        self.assertConfigError(errors, "unrecognized keys in")

    def test_load_mq_defaults(self) -> None:
        self.cfg.load_mq(self.filename, {})
        self.assertResults(mq={"type": 'simple'})

    def test_load_mq_explicit_type(self) -> None:
        self.cfg.load_mq(self.filename, {"mq": {"type": 'simple'}})
        self.assertResults(mq={"type": 'simple'})

    def test_load_mq_unk_type(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_mq(self.filename, {'mq': {'type': 'foo'}})

        self.assertConfigError(errors, "mq type 'foo' is not known")

    def test_load_mq_unk_keys(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_mq(self.filename, {'mq': {'bar': 'bar'}})

        self.assertConfigError(errors, "unrecognized keys in")

    def test_load_metrics_defaults(self) -> None:
        self.cfg.load_metrics(self.filename, {})
        self.assertResults(metrics=None)

    def test_load_metrics_invalid(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_metrics(self.filename, {'metrics': 13})

        self.assertConfigError(errors, "must be a dictionary")

    def test_load_metrics(self) -> None:
        self.cfg.load_metrics(self.filename, {"metrics": {"foo": 1}})
        self.assertResults(metrics={"foo": 1})

    def test_load_caches_defaults(self) -> None:
        self.cfg.load_caches(self.filename, {})
        self.assertResults(caches={"Changes": 10, "Builds": 15})

    def test_load_caches_invalid(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_caches(self.filename, {'caches': 13})

        self.assertConfigError(errors, "must be a dictionary")

    def test_load_caches_buildCacheSize(self) -> None:
        self.cfg.load_caches(self.filename, {"buildCacheSize": 13})
        self.assertResults(caches={"Builds": 13, "Changes": 10})

    def test_load_caches_buildCacheSize_and_caches(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_caches(self.filename, {'buildCacheSize': 13, 'caches': {'builds': 11}})

        self.assertConfigError(errors, "cannot specify")

    def test_load_caches_changeCacheSize(self) -> None:
        self.cfg.load_caches(self.filename, {"changeCacheSize": 13})
        self.assertResults(caches={"Changes": 13, "Builds": 15})

    def test_load_caches_changeCacheSize_and_caches(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_caches(self.filename, {'changeCacheSize': 13, 'caches': {'changes': 11}})

        self.assertConfigError(errors, "cannot specify")

    def test_load_caches(self) -> None:
        self.cfg.load_caches(self.filename, {"caches": {"foo": 1}})
        self.assertResults(caches={"Changes": 10, "Builds": 15, "foo": 1})

    def test_load_caches_not_int_err(self) -> None:
        """
        Test that non-integer cache sizes are not allowed.
        """
        with capture_config_errors() as errors:
            self.cfg.load_caches(self.filename, {'caches': {'foo': "1"}})

        self.assertConfigError(errors, "value for cache size 'foo' must be an integer")

    def test_load_caches_to_small_err(self) -> None:
        """
        Test that cache sizes less then 1 are not allowed.
        """
        with capture_config_errors() as errors:
            self.cfg.load_caches(self.filename, {'caches': {'Changes': -12}})

        self.assertConfigError(errors, "'Changes' cache size must be at least 1, got '-12'")

    def test_load_schedulers_defaults(self) -> None:
        self.cfg.load_schedulers(self.filename, {})
        self.assertResults(schedulers={})

    def test_load_schedulers_not_list(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_schedulers(self.filename, {'schedulers': {}})

        self.assertConfigError(errors, "must be a list of")

    def test_load_schedulers_not_instance(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_schedulers(self.filename, {'schedulers': [mock.Mock()]})

        self.assertConfigError(errors, "must be a list of")

    def test_load_schedulers_dupe(self) -> None:
        with capture_config_errors() as errors:
            sch1 = FakeScheduler(name='sch')
            sch2 = FakeScheduler(name='sch')
            self.cfg.load_schedulers(self.filename, {'schedulers': [sch1, sch2]})
        self.assertConfigError(errors, "scheduler name 'sch' used multiple times")

    def test_load_schedulers(self) -> None:
        sch = schedulers_base.ReconfigurableBaseScheduler(name='sch', builderNames=["a"])
        self.cfg.load_schedulers(self.filename, {"schedulers": [sch]})
        self.assertResults(schedulers={"sch": sch})

    def test_load_builders_defaults(self) -> None:
        self.cfg.load_builders(self.filename, {})
        self.assertResults(builders=[])

    def test_load_builders_not_list(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_builders(self.filename, {'builders': {}})

        self.assertConfigError(errors, "must be a list")

    def test_load_builders_not_instance(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_builders(self.filename, {'builders': [mock.Mock()]})
        self.assertConfigError(errors, "is not a builder config (in c['builders']")

    def test_load_builders(self) -> None:
        bldr = config.BuilderConfig(name='x', factory=factory.BuildFactory(), workername='x')
        self.cfg.load_builders(self.filename, {"builders": [bldr]})
        self.assertResults(builders=[bldr])

    def test_load_builders_dict(self) -> None:
        bldr = {"name": 'x', "factory": factory.BuildFactory(), "workername": 'x'}
        self.cfg.load_builders(self.filename, {"builders": [bldr]})
        self.assertIsInstance(self.cfg.builders[0], config.BuilderConfig)
        self.assertEqual(self.cfg.builders[0].name, 'x')

    def test_load_builders_abs_builddir(self) -> None:
        bldr = {
            "name": 'x',
            "factory": factory.BuildFactory(),
            "workername": 'x',
            "builddir": os.path.abspath('.'),
        }
        self.cfg.load_builders(self.filename, {"builders": [bldr]})
        self.assertEqual(len(self.flushWarnings([self.cfg.load_builders])), 1)

    def test_load_codebases_defaults(self) -> None:
        self.cfg.load_codebases(self.filename, {})
        self.assertResults(codebases=[])

    def test_load_codebases_not_list(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_codebases(self.filename, {'codebases': {}})
        self.assertConfigError(errors, "must be a list")

    def test_load_codebases_not_instance(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_codebases(self.filename, {'codebases': [mock.Mock()]})

        self.assertConfigError(errors, "is not a codebase config")

    def test_load_codebases_not_project(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_codebases(
                self.filename, {'codebases': [Codebase(name='codebase', project='project')]}
            )

        self.assertConfigError(errors, "includes unknown project")

    def test_load_codebases_valid(self) -> None:
        cfg = {
            'projects': [Project(name='project')],
            'codebases': [Codebase(name='codebase', project='project')],
        }

        self.cfg.load_projects(self.filename, cfg)
        self.cfg.load_codebases(self.filename, cfg)

        self.assertResults(codebases=[Codebase(name='codebase', project='project')])

    def test_load_workers_defaults(self) -> None:
        self.cfg.load_workers(self.filename, {})
        self.assertResults(workers=[])

    def test_load_workers_not_list(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_workers(self.filename, {'workers': {}})
        self.assertConfigError(errors, "must be a list")

    def test_load_workers_not_instance(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_workers(self.filename, {'workers': [mock.Mock()]})

        self.assertConfigError(errors, "must be a list of")

    @parameterized.expand(['debug', 'change', 'status'])
    def test_load_workers_reserved_names(self, worker_name: str) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_workers(self.filename, {'workers': [worker.Worker(worker_name, 'x')]})

        self.assertConfigError(errors, "is reserved")

    @parameterized.expand([
        ('initial_digits', "123_text_text"),
        ("spaces", "text text"),
        ("slash", "a/b"),
        ("dot", "a.b"),
    ])
    def test_load_workers_not_identifiers(self, name: str, worker_name: str) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_workers(self.filename, {'workers': [worker.Worker(worker_name, 'x')]})

        self.assertConfigError(errors, "is not an identifier")

    def test_load_workers_too_long(self) -> None:
        with capture_config_errors() as errors:
            name = "a" * 51
            self.cfg.load_workers(self.filename, {'workers': [worker.Worker(name, 'x')]})

        self.assertConfigError(errors, "is longer than")

    def test_load_workers_empty(self) -> None:
        with capture_config_errors() as errors:
            name = ""
            self.cfg.load_workers(self.filename, {'workers': [worker.Worker(name, 'x')]})
            errors.errors[:] = errors.errors[1:2]  # only get necessary error

        self.assertConfigError(errors, "cannot be an empty string")

    def test_load_workers(self) -> None:
        wrk = worker.Worker('foo', 'x')
        self.cfg.load_workers(self.filename, {"workers": [wrk]})
        self.assertResults(workers=[wrk])

    def test_load_change_sources_defaults(self) -> None:
        self.cfg.load_change_sources(self.filename, {})
        self.assertResults(change_sources=[])

    def test_load_change_sources_not_instance(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_change_sources(self.filename, {'change_source': [mock.Mock()]})

        self.assertConfigError(errors, "must be a list of")

    def test_load_change_sources_single(self) -> None:
        chsrc = FakeChangeSource()
        self.cfg.load_change_sources(self.filename, {"change_source": chsrc})
        self.assertResults(change_sources=[chsrc])

    def test_load_change_sources_list(self) -> None:
        chsrc = FakeChangeSource()
        self.cfg.load_change_sources(self.filename, {"change_source": [chsrc]})
        self.assertResults(change_sources=[chsrc])

    def test_load_machines_defaults(self) -> None:
        self.cfg.load_machines(self.filename, {})
        self.assertResults(machines=[])

    def test_load_machines_not_instance(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_machines(self.filename, {'machines': [mock.Mock()]})

        self.assertConfigError(errors, "must be a list of")

    def test_load_machines_single(self) -> None:
        with capture_config_errors() as errors:
            mm = FakeMachine(name='a')
            self.cfg.load_machines(self.filename, {'machines': mm})

        self.assertConfigError(errors, "must be a list of")

    def test_load_machines_list(self) -> None:
        mm = FakeMachine()
        self.cfg.load_machines(self.filename, {"machines": [mm]})
        self.assertResults(machines=[mm])

    def test_load_user_managers_defaults(self) -> None:
        self.cfg.load_user_managers(self.filename, {})
        self.assertResults(user_managers=[])

    def test_load_user_managers_not_list(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_user_managers(self.filename, {'user_managers': 'foo'})

        self.assertConfigError(errors, "must be a list")

    def test_load_user_managers(self) -> None:
        um = mock.Mock()
        self.cfg.load_user_managers(self.filename, {"user_managers": [um]})
        self.assertResults(user_managers=[um])

    def test_load_www_default(self) -> None:
        self.cfg.load_www(self.filename, {})
        self.assertResults(
            www={
                "port": None,
                "plugins": {},
                "auth": {'name': 'NoAuth'},
                "authz": {},
                "avatar_methods": {'name': 'gravatar'},
                "logfileName": 'http.log',
            }
        )

    def test_load_www_port(self) -> None:
        self.cfg.load_www(self.filename, {"www": {"port": 9888}})
        self.assertResults(
            www={
                "port": 9888,
                "plugins": {},
                "auth": {'name': 'NoAuth'},
                "authz": {},
                "avatar_methods": {'name': 'gravatar'},
                "logfileName": 'http.log',
            }
        )

    def test_load_www_plugin(self) -> None:
        self.cfg.load_www(self.filename, {"www": {"plugins": {'waterfall': {'foo': 'bar'}}}})
        self.assertResults(
            www={
                "port": None,
                "plugins": {'waterfall': {'foo': 'bar'}},
                "auth": {'name': 'NoAuth'},
                "authz": {},
                "avatar_methods": {'name': 'gravatar'},
                "logfileName": 'http.log',
            }
        )

    def test_load_www_allowed_origins(self) -> None:
        self.cfg.load_www(self.filename, {"www": {"allowed_origins": ['a', 'b']}})
        self.assertResults(
            www={
                "port": None,
                "allowed_origins": ['a', 'b'],
                "plugins": {},
                "auth": {'name': 'NoAuth'},
                "authz": {},
                "avatar_methods": {'name': 'gravatar'},
                "logfileName": 'http.log',
            }
        )

    def test_load_www_logfileName(self) -> None:
        self.cfg.load_www(self.filename, {"www": {"logfileName": 'http-access.log'}})
        self.assertResults(
            www={
                "port": None,
                "plugins": {},
                "auth": {'name': 'NoAuth'},
                "authz": {},
                "avatar_methods": {'name': 'gravatar'},
                "logfileName": 'http-access.log',
            }
        )

    def test_load_www_versions(self) -> None:
        custom_versions = [
            ('Test Custom Component', '0.0.1'),
            ('Test Custom Component 2', '0.1.0'),
        ]
        self.cfg.load_www(self.filename, {'www': {"versions": custom_versions}})
        self.assertResults(
            www={
                "port": None,
                "plugins": {},
                "auth": {'name': 'NoAuth'},
                "authz": {},
                "avatar_methods": {'name': 'gravatar'},
                "versions": custom_versions,
                "logfileName": 'http.log',
            }
        )

    def test_load_www_versions_not_list(self) -> None:
        with capture_config_errors() as errors:
            custom_versions = {
                'Test Custom Component': '0.0.1',
                'Test Custom Component 2': '0.0.2',
            }
            self.cfg.load_www(self.filename, {'www': {'versions': custom_versions}})
        self.assertConfigError(errors, 'Invalid www configuration value of versions')

    def test_load_www_versions_value_invalid(self) -> None:
        with capture_config_errors() as errors:
            custom_versions = [('a', '1'), 'abc', ('b',)]
            self.cfg.load_www(self.filename, {'www': {'versions': custom_versions}})

        self.assertConfigError(errors, 'Invalid www configuration value of versions')

    def test_load_www_cookie_expiration_time_not_timedelta(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_www(self.filename, {'www': {"cookie_expiration_time": 1}})

        self.assertConfigError(errors, 'Invalid www["cookie_expiration_time"]')

    def test_load_www_unknown(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.load_www(self.filename, {"www": {"foo": "bar"}})

        self.assertConfigError(errors, "unknown www configuration parameter(s) foo")

    def test_load_services_nominal(self) -> None:
        testcase = self

        class MyService(service.BuildbotService):
            def reconfigService(self, foo: str | None = None) -> None:
                testcase.foo = foo  # type: ignore[attr-defined]

        myService = MyService(foo="bar", name="foo")

        self.cfg.load_services(self.filename, {"services": [myService]})
        self.assertResults(services={"foo": myService})

    def test_load_services_badservice(self) -> None:
        class MyService:
            pass

        with capture_config_errors() as errors:
            myService = MyService()
            self.cfg.load_services(self.filename, {'services': [myService]})

        errMsg = (
            "<class 'buildbot.test.unit.config.test_master."
            "MasterConfig_loaders.test_load_services_badservice."
            "<locals>.MyService'> "
        )
        errMsg += "object should be an instance of buildbot.util.service.BuildbotService"
        self.assertConfigError(errors, errMsg)

    def test_load_services_duplicate(self) -> None:
        with capture_config_errors() as errors:

            class MyService(service.BuildbotService):
                name = 'myservice'

                def reconfigService(self, x: str | None = None) -> None:
                    self.x = x

            self.cfg.load_services(
                self.filename, {"services": [MyService(x='a'), MyService(x='b')]}
            )

        self.assertConfigError(errors, f'Duplicate service name {MyService.name!r}')

    def test_load_configurators_norminal(self) -> None:
        class MyConfigurator(configurators.ConfiguratorBase):
            def configure(self, config_dict: dict[str, Any]) -> None:
                config_dict['foo'] = 'bar'

        c = {"configurators": [MyConfigurator()]}
        self.cfg.run_configurators(self.filename, c)
        self.assertEqual(c['foo'], 'bar')


class MasterConfig_checkers(ConfigErrorsMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = config.master.MasterConfig()

    # utils

    def setup_basic_attrs(self) -> None:
        # set up a basic config for checking; this will be modified below
        sch = mock.Mock()
        sch.name = 'sch'
        sch.listBuilderNames = lambda: ['b1', 'b2']

        b1 = mock.Mock()
        b1.name = 'b1'

        b2 = mock.Mock()
        b2.name = 'b2'

        self.cfg.schedulers = {"sch": sch}
        self.cfg.workers = [mock.Mock()]
        self.cfg.builders = [b1, b2]

    def setup_builder_locks(
        self,
        builder_lock: str | None = None,
        dup_builder_lock: bool = False,
        bare_builder_lock: bool = False,
    ) -> None:
        """Set-up two mocked builders with specified locks.

        @type  builder_lock: string or None
        @param builder_lock: Name of the lock to add to first builder.
                             If None, no lock is added.

        @type dup_builder_lock: boolean
        @param dup_builder_lock: if True, add a lock with duplicate name
                                 to the second builder

        @type dup_builder_lock: boolean
        @param bare_builder_lock: if True, add bare lock objects, don't wrap
                                  them into locks.LockAccess object
        """

        def bldr(name: str) -> mock.Mock:
            b = mock.Mock()
            b.name = name
            b.locks = []
            b.factory.steps = [('cls', (), {"locks": []})]
            return b

        def lock(name: str) -> locks.MasterLock | locks.LockAccess:
            lock = locks.MasterLock(name)
            if bare_builder_lock:
                return lock
            return locks.LockAccess(lock, "counting", count=1)

        b1 = bldr('b1')
        b2 = bldr('b2')
        self.cfg.builders = [b1, b2]
        if builder_lock:
            b1.locks.append(lock(builder_lock))
            if dup_builder_lock:
                b2.locks.append(lock(builder_lock))

    # tests

    def test_check_single_master_multimaster(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.multiMaster = True
            self.cfg.check_single_master()

        self.assertNoConfigErrors(errors)

    def test_check_single_master_no_builders(self) -> None:
        with capture_config_errors() as errors:
            self.setup_basic_attrs()
            self.cfg.builders = []
            self.cfg.check_single_master()

        self.assertConfigError(errors, "no builders are configured")

    def test_check_single_master_no_workers(self) -> None:
        with capture_config_errors() as errors:
            self.setup_basic_attrs()
            self.cfg.workers = []
            self.cfg.check_single_master()

        self.assertConfigError(errors, "no workers are configured")

    def test_check_single_master_unsch_builder(self) -> None:
        with capture_config_errors() as errors:
            self.setup_basic_attrs()
            b3 = mock.Mock()
            b3.name = 'b3'
            self.cfg.builders.append(b3)
            self.cfg.check_single_master()

        self.assertConfigError(errors, "have no schedulers to drive them")

    def test_check_single_master_renderable_builderNames(self) -> None:
        with capture_config_errors() as errors:
            self.setup_basic_attrs()
            b3 = mock.Mock()
            b3.name = 'b3'
            self.cfg.builders.append(b3)
            sch2 = mock.Mock()
            sch2.listBuilderNames = lambda: properties.Interpolate('%(prop:foo)s')
            self.cfg.schedulers['sch2'] = sch2
            self.cfg.check_single_master()

        self.assertNoConfigErrors(errors)

    def test_check_schedulers_unknown_builder(self) -> None:
        with capture_config_errors() as errors:
            self.setup_basic_attrs()
            del self.cfg.builders[1]  # remove b2, leaving b1

            self.cfg.check_schedulers()

        self.assertConfigError(errors, "Unknown builder 'b2'")

    def test_check_schedulers_ignored_in_multiMaster(self) -> None:
        with capture_config_errors() as errors:
            self.setup_basic_attrs()
            del self.cfg.builders[1]  # remove b2, leaving b1
            self.cfg.multiMaster = True
            self.cfg.check_schedulers()

        self.assertNoConfigErrors(errors)

    def test_check_schedulers_renderable_builderNames(self) -> None:
        with capture_config_errors() as errors:
            self.setup_basic_attrs()
            sch2 = mock.Mock()
            sch2.listBuilderNames = lambda: properties.Interpolate('%(prop:foo)s')
            self.cfg.schedulers['sch2'] = sch2

            self.cfg.check_schedulers()

        self.assertNoConfigErrors(errors)

    def test_check_schedulers(self) -> None:
        with capture_config_errors() as errors:
            self.setup_basic_attrs()
            self.cfg.check_schedulers()

        self.assertNoConfigErrors(errors)

    def test_check_locks_dup_builder_lock(self) -> None:
        with capture_config_errors() as errors:
            self.setup_builder_locks(builder_lock='l', dup_builder_lock=True)
            self.cfg.check_locks()

        self.assertConfigError(errors, "Two locks share")

    def test_check_locks(self) -> None:
        with capture_config_errors() as errors:
            self.setup_builder_locks(builder_lock='bl')
            self.cfg.check_locks()

        self.assertNoConfigErrors(errors)

    def test_check_locks_none(self) -> None:
        # no locks in the whole config, should be fine
        with capture_config_errors() as errors:
            self.setup_builder_locks()
            self.cfg.check_locks()

        self.assertNoConfigErrors(errors)

    def test_check_locks_bare(self) -> None:
        # check_locks() should be able to handle bare lock object,
        # lock objects that are not wrapped into LockAccess() object

        with capture_config_errors() as errors:
            self.setup_builder_locks(builder_lock='oldlock', bare_builder_lock=True)
            self.cfg.check_locks()

        self.assertNoConfigErrors(errors)

    def test_check_builders_unknown_worker(self) -> None:
        with capture_config_errors() as errors:
            wrk = mock.Mock()
            wrk.workername = 'xyz'
            self.cfg.workers = [wrk]

            b1 = FakeBuilder(workernames=['xyz', 'abc'], builddir='x', name='b1', project=None)
            self.cfg.builders = [b1]

            self.cfg.check_builders()
        self.assertConfigError(errors, "builder 'b1' uses unknown workers 'abc'")

    def test_check_builders_unknown_project(self) -> None:
        with capture_config_errors() as errors:
            wrk = mock.Mock()
            wrk.name = 'proj1'
            self.cfg.projects = [wrk]

            b1 = FakeBuilder(workernames=[], builddir='x', name='b1', project='proj_unknown')
            self.cfg.builders = [b1]

            self.cfg.check_builders()
        self.assertConfigError(errors, "builder 'b1' uses unknown project name 'proj_unknown'")

    def test_check_builders_duplicate_name(self) -> None:
        with capture_config_errors() as errors:
            b1 = FakeBuilder(workernames=[], name='b1', builddir='1', project=None)
            b2 = FakeBuilder(workernames=[], name='b1', builddir='2', project=None)
            self.cfg.builders = [b1, b2]

            self.cfg.check_builders()

        self.assertConfigError(errors, "duplicate builder name 'b1'")

    def test_check_builders_duplicate_builddir(self) -> None:
        with capture_config_errors() as errors:
            b1 = FakeBuilder(workernames=[], name='b1', builddir='dir', project=None)
            b2 = FakeBuilder(workernames=[], name='b2', builddir='dir', project=None)
            self.cfg.builders = [b1, b2]

            self.cfg.check_builders()

        self.assertConfigError(errors, "duplicate builder builddir 'dir'")

    def test_check_builders(self) -> None:
        with capture_config_errors() as errors:
            wrk = mock.Mock()
            wrk.workername = 'a'
            self.cfg.workers = [wrk]

            project = mock.Mock()
            project.name = 'proj1'
            self.cfg.projects = [project]

            b1 = FakeBuilder(workernames=['a'], name='b1', builddir='dir1', project='proj1')
            b2 = FakeBuilder(workernames=['a'], name='b2', builddir='dir2', project=None)
            self.cfg.builders = [b1, b2]

            self.cfg.check_builders()

        self.assertNoConfigErrors(errors)

    def test_check_duplicate_projects(self) -> None:
        with capture_config_errors() as errors:
            project1 = mock.Mock()
            project1.name = 'proj1'
            project2 = mock.Mock()
            project2.name = 'proj1'
            self.cfg.projects = [project1, project2]

            self.cfg.check_projects()

        self.assertConfigError(errors, "duplicate project name 'proj1'")

    def test_check_ports_protocols_set(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.protocols = {"pb": {"port": 10}}
            self.cfg.check_ports()

        self.assertNoConfigErrors(errors)

    def test_check_ports_protocols_not_set_workers(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.workers = [mock.Mock()]
            self.cfg.check_ports()

        self.assertConfigError(errors, "workers are configured, but c['protocols'] not")

    def test_check_ports_protocols_port_duplication(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.protocols = {"pb": {"port": 123}, "amp": {"port": 123}}
            self.cfg.check_ports()

        self.assertConfigError(errors, "Some of ports in c['protocols'] duplicated")

    def test_check_machines_unknown_name(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.workers = [FakeWorker(name='wa', machine_name='unk')]
            self.cfg.machines = [FakeMachine(name='a')]
            self.cfg.check_machines()

        self.assertConfigError(errors, 'uses unknown machine')

    def test_check_machines_duplicate_name(self) -> None:
        with capture_config_errors() as errors:
            self.cfg.machines = [FakeMachine(name='a'), FakeMachine(name='a')]
            self.cfg.check_machines()

        self.assertConfigError(errors, 'duplicate machine name')


class MasterConfig_old_worker_api(unittest.TestCase):
    filename = "test.cfg"

    def setUp(self) -> None:
        self.cfg = config.master.MasterConfig()

    def test_workers_new_api(self) -> None:
        with assertNotProducesWarnings(DeprecatedApiWarning):
            self.assertEqual(self.cfg.workers, [])


class FakeService(service.ReconfigurableServiceMixin, service.AsyncService):
    succeed = True
    call_index = 1

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(
        self, new_config: MasterConfig
    ) -> InlineCallbacksType[None]:
        self.called = FakeService.call_index
        FakeService.call_index += 1
        yield super().reconfigServiceWithBuildbotConfig(new_config)
        if not self.succeed:
            raise ValueError("oh noes")


class FakeMultiService(service.ReconfigurableServiceMixin, service.AsyncMultiService):
    def reconfigServiceWithBuildbotConfig(self, new_config: MasterConfig) -> defer.Deferred[None]:
        self.called = True
        d = super().reconfigServiceWithBuildbotConfig(new_config)
        return d


class ReconfigurableServiceMixin(unittest.TestCase):
    @defer.inlineCallbacks
    def test_service(self) -> InlineCallbacksType[None]:
        svc = FakeService()
        yield svc.reconfigServiceWithBuildbotConfig(mock.Mock())

        self.assertTrue(svc.called)

    @defer.inlineCallbacks
    def test_service_failure(self) -> InlineCallbacksType[None]:
        svc = FakeService()
        svc.succeed = False
        try:
            yield svc.reconfigServiceWithBuildbotConfig(mock.Mock())
        except ValueError:
            pass
        else:
            self.fail("should have raised ValueError")

    @defer.inlineCallbacks
    def test_multiservice(self) -> InlineCallbacksType[None]:
        svc = FakeMultiService()
        ch1 = FakeService()
        yield ch1.setServiceParent(svc)
        ch2 = FakeMultiService()
        yield ch2.setServiceParent(svc)
        ch3 = FakeService()
        yield ch3.setServiceParent(ch2)
        yield svc.reconfigServiceWithBuildbotConfig(mock.Mock())

        self.assertTrue(svc.called)
        self.assertTrue(ch1.called)
        self.assertTrue(ch2.called)
        self.assertTrue(ch3.called)

    @defer.inlineCallbacks
    def test_multiservice_priority(self) -> InlineCallbacksType[None]:
        parent = FakeMultiService()
        svc128 = FakeService()
        yield svc128.setServiceParent(parent)

        services = [svc128]
        for i in range(20, 1, -1):
            svc = FakeService()
            svc.reconfig_priority = i
            yield svc.setServiceParent(parent)
            services.append(svc)

        yield parent.reconfigServiceWithBuildbotConfig(mock.Mock())

        prio_order = [s.called for s in services]
        called_order = sorted(prio_order)
        self.assertEqual(prio_order, called_order)

    @defer.inlineCallbacks
    def test_multiservice_nested_failure(self) -> InlineCallbacksType[None]:
        svc = FakeMultiService()
        ch1 = FakeService()
        yield ch1.setServiceParent(svc)
        ch1.succeed = False
        try:
            yield svc.reconfigServiceWithBuildbotConfig(mock.Mock())
        except ValueError:
            pass
        else:
            self.fail("should have raised ValueError")

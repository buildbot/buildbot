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

# We cannot use the builtins module here from Python-Future.
# We need to use the native __builtin__ module on Python 2,
# and builtins module on Python 3, because we need to override
# the actual native open method.

from __future__ import absolute_import
from __future__ import print_function
from future.builtins import range
from future.utils import PY3
from future.utils import iteritems

import os
import re
import textwrap

import mock

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
from buildbot.process import factory
from buildbot.process import properties
from buildbot.schedulers import base as schedulers_base
from buildbot.status import base as status_base
from buildbot.test.util import dirs
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.util import service
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning

try:
    # Python 2
    import __builtin__ as builtins
except ImportError:
    # Python 3
    import builtins

global_defaults = dict(
    title='Buildbot',
    titleURL='http://buildbot.net',
    buildbotURL='http://localhost:8080/',
    logCompressionLimit=4096,
    logCompressionMethod='gz',
    logEncoding='utf-8',
    logMaxTailSize=None,
    logMaxSize=None,
    properties=properties.Properties(),
    collapseRequests=None,
    prioritizeBuilders=None,
    protocols={},
    multiMaster=False,
    manhole=None,
    buildbotNetUsageData=None,  # in unit tests we default to None, but normally defaults to 'basic'
    www=dict(port=None, plugins={},
             auth={'name': 'NoAuth'}, authz={},
             avatar_methods={'name': 'gravatar'},
             logfileName='http.log'),
)


class FakeChangeSource(changes_base.ChangeSource):

    def __init__(self):
        changes_base.ChangeSource.__init__(self, name='FakeChangeSource')


class FakeStatusReceiver(status_base.StatusReceiver):
    pass


@implementer(interfaces.IScheduler)
class FakeScheduler(object):

    def __init__(self, name):
        self.name = name


class FakeBuilder(object):

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class ConfigErrors(unittest.TestCase):

    def test_constr(self):
        ex = config.ConfigErrors(['a', 'b'])
        self.assertEqual(ex.errors, ['a', 'b'])

    def test_addError(self):
        ex = config.ConfigErrors(['a'])
        ex.addError('c')
        self.assertEqual(ex.errors, ['a', 'c'])

    def test_nonempty(self):
        empty = config.ConfigErrors()
        full = config.ConfigErrors(['a'])
        self.assertTrue(not empty)
        self.assertFalse(not full)

    def test_error_raises(self):
        e = self.assertRaises(config.ConfigErrors, config.error, "message")
        self.assertEqual(e.errors, ["message"])

    def test_error_no_raise(self):
        e = config.ConfigErrors()
        self.patch(config, "_errors", e)
        config.error("message")
        self.assertEqual(e.errors, ["message"])

    def test_str(self):
        ex = config.ConfigErrors()
        self.assertEqual(str(ex), "")

        ex = config.ConfigErrors(["a"])
        self.assertEqual(str(ex), "a")

        ex = config.ConfigErrors(["a", "b"])
        self.assertEqual(str(ex), "a\nb")

        ex = config.ConfigErrors(["a"])
        ex.addError('c')
        self.assertEqual(str(ex), "a\nc")


class ConfigLoaderTests(ConfigErrorsMixin, dirs.DirsMixin, unittest.SynchronousTestCase):

    def setUp(self):
        self.basedir = os.path.abspath('basedir')
        self.filename = os.path.join(self.basedir, 'test.cfg')
        self.patch(config, "_in_unit_tests", False)

        return self.setUpDirs('basedir')

    def tearDown(self):
        return self.tearDownDirs()

    def install_config_file(self, config_file, other_files={}):
        config_file = textwrap.dedent(config_file)
        with open(os.path.join(self.basedir, self.filename), "w") as f:
            f.write(config_file)
        for file, contents in iteritems(other_files):
            with open(file, "w") as f:
                f.write(contents)

    def test_loadConfig_missing_file(self):
        self.assertRaisesConfigError(
            re.compile("configuration file .* does not exist"),
            lambda: config.loadConfigDict(self.basedir, self.filename))

    def test_loadConfig_missing_basedir(self):
        self.assertRaisesConfigError(
            re.compile("basedir .* does not exist"),
            lambda: config.loadConfigDict(os.path.join(self.basedir, 'NO'), 'test.cfg'))

    def test_loadConfig_open_error(self):
        """
        Check that loadConfig() raises correct ConfigError exception in cases
        when configure file is found, but we fail to open it.
        """

        def raise_IOError(*args):
            raise IOError("error_msg")

        self.install_config_file('#dummy')

        # override build-in open() function to always rise IOError
        self.patch(builtins, "open", raise_IOError)

        # check that we got the expected ConfigError exception
        self.assertRaisesConfigError(
            re.compile("unable to open configuration file .*: error_msg"),
            lambda: config.loadConfigDict(self.basedir, self.filename))

    def test_loadConfig_parse_error(self):
        self.install_config_file('def x:\nbar')
        self.assertRaisesConfigError(
            re.compile("encountered a SyntaxError while parsing config file:"),
            lambda: config.loadConfigDict(self.basedir, self.filename))

    def test_loadConfig_eval_ConfigError(self):
        self.install_config_file("""\
                from buildbot import config
                BuildmasterConfig = { 'multiMaster': True }
                config.error('oh noes!')""")
        self.assertRaisesConfigError("oh noes",
                                     lambda: config.loadConfigDict(self.basedir, self.filename))

    def test_loadConfig_eval_otherError(self):
        self.install_config_file("""\
                from buildbot import config
                BuildmasterConfig = { 'multiMaster': True }
                raise ValueError('oh noes')""")
        self.assertRaisesConfigError("error while parsing config file: oh noes (traceback in logfile)",
                                     lambda: config.loadConfigDict(self.basedir, self.filename))

        [error] = self.flushLoggedErrors(ValueError)
        self.assertEqual(error.value.args, ("oh noes",))

    def test_loadConfig_no_BuildmasterConfig(self):
        self.install_config_file('x=10')
        self.assertRaisesConfigError("does not define 'BuildmasterConfig'",
                                     lambda: config.loadConfigDict(self.basedir, self.filename))

    def test_loadConfig_with_local_import(self):
        self.install_config_file("""\
                from subsidiary_module import x
                BuildmasterConfig = dict(x=x)
                """,
                                 {'basedir/subsidiary_module.py': "x = 10"})
        _, rv = config.loadConfigDict(self.basedir, self.filename)
        self.assertEqual(rv, {'x': 10})


class MasterConfig(ConfigErrorsMixin, dirs.DirsMixin, unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.basedir = os.path.abspath('basedir')
        self.filename = os.path.join(self.basedir, 'test.cfg')
        return self.setUpDirs('basedir')

    def tearDown(self):
        return self.tearDownDirs()

    # utils

    def patch_load_helpers(self):
        # patch out all of the "helpers" for loadConfig with null functions
        for n in dir(config.MasterConfig):
            if n.startswith('load_'):
                typ = 'loader'
            elif n.startswith('check_'):
                typ = 'checker'
            else:
                continue

            v = getattr(config.MasterConfig, n)
            if callable(v):
                if typ == 'loader':
                    self.patch(config.MasterConfig, n,
                               mock.Mock(side_effect=lambda filename,
                                         config_dict: None))
                else:
                    self.patch(config.MasterConfig, n,
                               mock.Mock(side_effect=lambda: None))

    def install_config_file(self, config_file, other_files={}):
        config_file = textwrap.dedent(config_file)
        with open(os.path.join(self.basedir, self.filename), "w") as f:
            f.write(config_file)
        for file, contents in iteritems(other_files):
            with open(file, "w") as f:
                f.write(contents)
    # tests

    def test_defaults(self):
        cfg = config.MasterConfig()
        expected = dict(
            # validation,
            db=dict(
                db_url='sqlite:///state.sqlite'),
            mq=dict(type='simple'),
            metrics=None,
            caches=dict(Changes=10, Builds=15),
            schedulers={},
            builders=[],
            workers=[],
            change_sources=[],
            status=[],
            user_managers=[],
            revlink=revlinks.default_revlink_matcher
        )
        expected.update(global_defaults)
        expected['buildbotNetUsageData'] = 'basic'
        got = dict([
            (attr, getattr(cfg, attr))
            for attr, exp in iteritems(expected)])
        got = interfaces.IConfigured(got).getConfigDict()
        expected = interfaces.IConfigured(expected).getConfigDict()
        self.assertEqual(got, expected)

    def test_defaults_validation(self):
        # re's aren't comparable, but we can make sure the keys match
        cfg = config.MasterConfig()
        self.assertEqual(sorted(cfg.validation.keys()),
                         sorted([
                             'branch', 'revision', 'property_name', 'property_value',
                         ]))

    def test_loadConfig_eval_ConfigErrors(self):
        # We test a config that has embedded errors, as well
        # as semantic errors that get added later. If an exception is raised
        # prematurely, then the semantic errors wouldn't get reported.
        self.install_config_file("""\
                from buildbot import config
                BuildmasterConfig = {}
                config.error('oh noes!')
                config.error('noes too!')""")
        e = self.assertRaises(config.ConfigErrors,
                              config.FileLoader(self.basedir, self.filename).loadConfig)
        self.assertEqual(e.errors, ['oh noes!', 'noes too!',
                                    'no workers are configured',
                                    'no builders are configured'])

    def test_loadConfig_unknown_key(self):
        self.patch_load_helpers()
        self.install_config_file("""\
                BuildmasterConfig = dict(foo=10)
                """)
        self.assertRaisesConfigError("Unknown BuildmasterConfig key foo",
                                     config.FileLoader(self.basedir, self.filename).loadConfig)

    def test_loadConfig_unknown_keys(self):
        self.patch_load_helpers()
        self.install_config_file("""\
                BuildmasterConfig = dict(foo=10, bar=20)
                """)
        self.assertRaisesConfigError("Unknown BuildmasterConfig keys bar, foo",
                                     config.FileLoader(self.basedir, self.filename).loadConfig)

    def test_loadConfig_success(self):
        self.patch_load_helpers()
        self.install_config_file("""\
                BuildmasterConfig = dict()
                """)
        rv = config.FileLoader(self.basedir, self.filename).loadConfig()
        self.assertIsInstance(rv, config.MasterConfig)

        # make sure all of the loaders and checkers are called
        self.assertTrue(rv.load_global.called)
        self.assertTrue(rv.load_validation.called)
        self.assertTrue(rv.load_db.called)
        self.assertTrue(rv.load_metrics.called)
        self.assertTrue(rv.load_caches.called)
        self.assertTrue(rv.load_schedulers.called)
        self.assertTrue(rv.load_builders.called)
        self.assertTrue(rv.load_workers.called)
        self.assertTrue(rv.load_change_sources.called)
        self.assertTrue(rv.load_status.called)
        self.assertTrue(rv.load_user_managers.called)

        self.assertTrue(rv.check_single_master.called)
        self.assertTrue(rv.check_schedulers.called)
        self.assertTrue(rv.check_locks.called)
        self.assertTrue(rv.check_builders.called)
        self.assertTrue(rv.check_status.called)
        self.assertTrue(rv.check_ports.called)

    def test_preChangeGenerator(self):
        cfg = config.MasterConfig()
        self.assertEqual({
            'author': None,
            'files': None,
            'comments': None,
            'revision': None,
            'when_timestamp': None,
            'branch': None,
            'category': None,
            'revlink': u'',
            'properties': {},
            'repository': u'',
            'project': u'',
            'codebase': None},
            cfg.preChangeGenerator())


class MasterConfig_loaders(ConfigErrorsMixin, unittest.TestCase):

    filename = 'test.cfg'

    def setUp(self):
        self.cfg = config.MasterConfig()
        self.errors = config.ConfigErrors()
        self.patch(config, '_errors', self.errors)

    # utils

    def assertResults(self, **expected):
        self.assertFalse(self.errors, self.errors.errors)
        got = dict([
            (attr, getattr(self.cfg, attr))
            for attr, exp in iteritems(expected)])
        got = interfaces.IConfigured(got).getConfigDict()
        expected = interfaces.IConfigured(expected).getConfigDict()

        self.assertEqual(got, expected)

    # tests

    def test_load_global_defaults(self):
        self.maxDiff = None
        self.cfg.load_global(self.filename, {})
        self.assertResults(**global_defaults)

    def test_load_global_string_param_not_string(self):
        self.cfg.load_global(self.filename,
                             dict(title=10))
        self.assertConfigError(self.errors, 'must be a string')

    def test_load_global_int_param_not_int(self):
        self.cfg.load_global(self.filename,
                             dict(changeHorizon='yes'))
        self.assertConfigError(self.errors, 'must be an int')

    def test_load_global_protocols_not_dict(self):
        self.cfg.load_global(self.filename,
                             dict(protocols="test"))
        self.assertConfigError(self.errors, "c['protocols'] must be dict")

    def test_load_global_when_slavePortnum_and_protocols_set(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=r"c\['slavePortnum'\] key is deprecated"):
            self.cfg.load_global(self.filename,
                                 dict(protocols={"pb": {"port": 123}}, slavePortnum=321))
        self.assertConfigError(self.errors,
                               "Both c['slavePortnum'] and c['protocols']['pb']['port']"
                               " defined, recommended to remove slavePortnum and leave"
                               " only c['protocols']['pb']['port']")

    def test_load_global_protocols_key_int(self):
        self.cfg.load_global(self.filename,
                             dict(protocols={321: {"port": 123}}))
        self.assertConfigError(
            self.errors, "c['protocols'] keys must be strings")

    def test_load_global_protocols_value_not_dict(self):
        self.cfg.load_global(self.filename,
                             dict(protocols={"pb": 123}))
        self.assertConfigError(
            self.errors, "c['protocols']['pb'] must be a dict")

    def do_test_load_global(self, config_dict, **expected):
        self.cfg.load_global(self.filename, config_dict)
        self.assertResults(**expected)

    def test_load_global_title(self):
        self.do_test_load_global(dict(title='hi'), title='hi')

    def test_load_global_projectURL(self):
        self.do_test_load_global(dict(projectName='hey'), title='hey')

    def test_load_global_titleURL(self):
        self.do_test_load_global(dict(titleURL='hi'), titleURL='hi')

    def test_load_global_buildbotURL(self):
        self.do_test_load_global(dict(buildbotURL='hey'), buildbotURL='hey')

    def test_load_global_changeHorizon(self):
        self.do_test_load_global(dict(changeHorizon=10), changeHorizon=10)

    def test_load_global_changeHorizon_none(self):
        self.do_test_load_global(dict(changeHorizon=None), changeHorizon=None)

    def test_load_global_eventHorizon(self):
        with assertProducesWarning(
                config.ConfigWarning,
                message_pattern=r"`eventHorizon` is deprecated and ignored"):
            self.do_test_load_global(
                dict(eventHorizon=10))

    def test_load_global_buildbotNetUsageData(self):
        self.patch(config, "_in_unit_tests", False)
        with assertProducesWarning(
                config.ConfigWarning,
                message_pattern=r"`buildbotNetUsageData` is not configured and defaults to basic."):
            self.do_test_load_global(
                dict())

    def test_load_global_logCompressionLimit(self):
        self.do_test_load_global(dict(logCompressionLimit=10),
                                 logCompressionLimit=10)

    def test_load_global_logCompressionMethod(self):
        self.do_test_load_global(dict(logCompressionMethod='bz2'),
                                 logCompressionMethod='bz2')

    def test_load_global_logCompressionMethod_invalid(self):
        self.cfg.load_global(self.filename,
                             dict(logCompressionMethod='foo'))
        self.assertConfigError(
            self.errors, "c['logCompressionMethod'] must be 'raw', 'bz2', 'gz' or 'lz4'")

    def test_load_global_codebaseGenerator(self):
        func = lambda _: "dummy"
        self.do_test_load_global(dict(codebaseGenerator=func),
                                 codebaseGenerator=func)

    def test_load_global_codebaseGenerator_invalid(self):
        self.cfg.load_global(self.filename,
                             dict(codebaseGenerator='dummy'))
        self.assertConfigError(self.errors,
                               "codebaseGenerator must be a callable "
                               "accepting a dict and returning a str")

    def test_load_global_logMaxSize(self):
        self.do_test_load_global(dict(logMaxSize=123), logMaxSize=123)

    def test_load_global_logMaxTailSize(self):
        self.do_test_load_global(dict(logMaxTailSize=123), logMaxTailSize=123)

    def test_load_global_logEncoding(self):
        self.do_test_load_global(
            dict(logEncoding='latin-2'), logEncoding='latin-2')

    def test_load_global_properties(self):
        exp = properties.Properties()
        exp.setProperty('x', 10, self.filename)
        self.do_test_load_global(dict(properties=dict(x=10)), properties=exp)

    def test_load_global_properties_invalid(self):
        self.cfg.load_global(self.filename,
                             dict(properties='yes'))
        self.assertConfigError(self.errors, "must be a dictionary")

    def test_load_global_collapseRequests_bool(self):
        self.do_test_load_global(dict(collapseRequests=False),
                                 collapseRequests=False)

    def test_load_global_collapseRequests_callable(self):
        callable = lambda: None
        self.do_test_load_global(dict(collapseRequests=callable),
                                 collapseRequests=callable)

    def test_load_global_collapseRequests_invalid(self):
        self.cfg.load_global(self.filename,
                             dict(collapseRequests='yes'))
        self.assertConfigError(self.errors,
                               "must be a callable, True, or False")

    def test_load_global_prioritizeBuilders_callable(self):
        callable = lambda: None
        self.do_test_load_global(dict(prioritizeBuilders=callable),
                                 prioritizeBuilders=callable)

    def test_load_global_prioritizeBuilders_invalid(self):
        self.cfg.load_global(self.filename,
                             dict(prioritizeBuilders='yes'))
        self.assertConfigError(self.errors, "must be a callable")

    def test_load_global_slavePortnum_int(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=r"c\['slavePortnum'\] key is deprecated"):
            self.do_test_load_global(dict(slavePortnum=123),
                                     protocols={'pb': {'port': 'tcp:123'}})

    def test_load_global_slavePortnum_str(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=r"c\['slavePortnum'\] key is deprecated"):
            self.do_test_load_global(dict(slavePortnum='udp:123'),
                                     protocols={'pb': {'port': 'udp:123'}})

    def test_load_global_protocols_str(self):
        self.do_test_load_global(dict(protocols={'pb': {'port': 'udp:123'}}),
                                 protocols={'pb': {'port': 'udp:123'}})

    def test_load_global_multiMaster(self):
        self.do_test_load_global(dict(multiMaster=1), multiMaster=1)

    def test_load_global_manhole(self):
        mh = mock.Mock(name='manhole')
        self.do_test_load_global(dict(manhole=mh), manhole=mh)

    def test_load_global_revlink_callable(self):
        callable = lambda: None
        self.do_test_load_global(dict(revlink=callable),
                                 revlink=callable)

    def test_load_global_revlink_invalid(self):
        self.cfg.load_global(self.filename, dict(revlink=''))
        self.assertConfigError(self.errors, "must be a callable")

    def test_load_validation_defaults(self):
        self.cfg.load_validation(self.filename, {})
        self.assertEqual(sorted(self.cfg.validation.keys()),
                         sorted([
                             'branch', 'revision', 'property_name', 'property_value',
                         ]))

    def test_load_validation_invalid(self):
        self.cfg.load_validation(self.filename,
                                 dict(validation='plz'))
        self.assertConfigError(self.errors, "must be a dictionary")

    def test_load_validation_unk_keys(self):
        self.cfg.load_validation(self.filename,
                                 dict(validation=dict(users='.*')))
        self.assertConfigError(self.errors, "unrecognized validation key(s)")

    def test_load_validation(self):
        r = re.compile('.*')
        self.cfg.load_validation(self.filename,
                                 dict(validation=dict(branch=r)))
        self.assertEqual(self.cfg.validation['branch'], r)
        # check that defaults are still around
        self.assertIn('revision', self.cfg.validation)

    def test_load_db_defaults(self):
        self.cfg.load_db(self.filename, {})
        self.assertResults(
            db=dict(db_url='sqlite:///state.sqlite'))

    def test_load_db_db_url(self):
        self.cfg.load_db(self.filename, dict(db_url='abcd'))
        self.assertResults(db=dict(db_url='abcd'))

    def test_load_db_db_poll_interval(self):
        # value is ignored, but no error
        with assertProducesWarning(
                config.ConfigWarning,
                message_pattern=r"db_poll_interval is deprecated and will be ignored"):
            self.cfg.load_db(self.filename, dict(db_poll_interval=2))
        self.assertResults(
            db=dict(db_url='sqlite:///state.sqlite'))

    def test_load_db_dict(self):
        # db_poll_interval value is ignored, but no error
        with assertProducesWarning(
                config.ConfigWarning,
                message_pattern=r"db_poll_interval is deprecated and will be ignored"):
            self.cfg.load_db(self.filename,
                             dict(db=dict(db_url='abcd', db_poll_interval=10)))
        self.assertResults(db=dict(db_url='abcd'))

    def test_load_db_unk_keys(self):
        with assertProducesWarning(
                config.ConfigWarning,
                message_pattern=r"db_poll_interval is deprecated and will be ignored"):
            self.cfg.load_db(self.filename,
                             dict(db=dict(db_url='abcd', db_poll_interval=10, bar='bar')))
        self.assertConfigError(self.errors, "unrecognized keys in")

    def test_load_mq_defaults(self):
        self.cfg.load_mq(self.filename, {})
        self.assertResults(mq=dict(type='simple'))

    def test_load_mq_explicit_type(self):
        self.cfg.load_mq(self.filename,
                         dict(mq=dict(type='simple')))
        self.assertResults(mq=dict(type='simple'))

    def test_load_mq_unk_type(self):
        self.cfg.load_mq(self.filename, dict(mq=dict(type='foo')))
        self.assertConfigError(self.errors, "mq type 'foo' is not known")

    def test_load_mq_unk_keys(self):
        self.cfg.load_mq(self.filename,
                         dict(mq=dict(bar='bar')))
        self.assertConfigError(self.errors, "unrecognized keys in")

    def test_load_metrics_defaults(self):
        self.cfg.load_metrics(self.filename, {})
        self.assertResults(metrics=None)

    def test_load_metrics_invalid(self):
        self.cfg.load_metrics(self.filename, dict(metrics=13))
        self.assertConfigError(self.errors, "must be a dictionary")

    def test_load_metrics(self):
        self.cfg.load_metrics(self.filename,
                              dict(metrics=dict(foo=1)))
        self.assertResults(metrics=dict(foo=1))

    def test_load_caches_defaults(self):
        self.cfg.load_caches(self.filename, {})
        self.assertResults(caches=dict(Changes=10, Builds=15))

    def test_load_caches_invalid(self):
        self.cfg.load_caches(self.filename, dict(caches=13))
        self.assertConfigError(self.errors, "must be a dictionary")

    def test_load_caches_buildCacheSize(self):
        self.cfg.load_caches(self.filename,
                             dict(buildCacheSize=13))
        self.assertResults(caches=dict(Builds=13, Changes=10))

    def test_load_caches_buildCacheSize_and_caches(self):
        self.cfg.load_caches(self.filename,
                             dict(buildCacheSize=13, caches=dict(builds=11)))
        self.assertConfigError(self.errors, "cannot specify")

    def test_load_caches_changeCacheSize(self):
        self.cfg.load_caches(self.filename,
                             dict(changeCacheSize=13))
        self.assertResults(caches=dict(Changes=13, Builds=15))

    def test_load_caches_changeCacheSize_and_caches(self):
        self.cfg.load_caches(self.filename,
                             dict(changeCacheSize=13, caches=dict(changes=11)))
        self.assertConfigError(self.errors, "cannot specify")

    def test_load_caches(self):
        self.cfg.load_caches(self.filename,
                             dict(caches=dict(foo=1)))
        self.assertResults(caches=dict(Changes=10, Builds=15, foo=1))

    def test_load_caches_not_int_err(self):
        """
        Test that non-integer cache sizes are not allowed.
        """
        self.cfg.load_caches(self.filename,
                             dict(caches=dict(foo="1")))
        self.assertConfigError(self.errors,
                               "value for cache size 'foo' must be an integer")

    def test_load_caches_to_small_err(self):
        """
        Test that cache sizes less then 1 are not allowed.
        """
        self.cfg.load_caches(self.filename, dict(caches=dict(Changes=-12)))
        self.assertConfigError(self.errors,
                               "'Changes' cache size must be at least 1, got '-12'")

    def test_load_schedulers_defaults(self):
        self.cfg.load_schedulers(self.filename, {})
        self.assertResults(schedulers={})

    def test_load_schedulers_not_list(self):
        self.cfg.load_schedulers(self.filename,
                                 dict(schedulers=dict()))
        self.assertConfigError(self.errors, "must be a list of")

    def test_load_schedulers_not_instance(self):
        self.cfg.load_schedulers(self.filename,
                                 dict(schedulers=[mock.Mock()]))
        self.assertConfigError(self.errors, "must be a list of")

    def test_load_schedulers_dupe(self):
        sch1 = FakeScheduler(name='sch')
        sch2 = FakeScheduler(name='sch')
        self.cfg.load_schedulers(self.filename,
                                 dict(schedulers=[sch1, sch2]))
        self.assertConfigError(self.errors,
                               "scheduler name 'sch' used multiple times")

    def test_load_schedulers(self):
        sch = schedulers_base.BaseScheduler('sch', [""])
        self.cfg.load_schedulers(self.filename,
                                 dict(schedulers=[sch]))
        self.assertResults(schedulers=dict(sch=sch))

    def test_load_builders_defaults(self):
        self.cfg.load_builders(self.filename, {})
        self.assertResults(builders=[])

    def test_load_builders_not_list(self):
        self.cfg.load_builders(self.filename,
                               dict(builders=dict()))
        self.assertConfigError(self.errors, "must be a list")

    def test_load_builders_not_instance(self):
        self.cfg.load_builders(self.filename,
                               dict(builders=[mock.Mock()]))
        self.assertConfigError(
            self.errors, "is not a builder config (in c['builders']")

    def test_load_builders(self):
        bldr = config.BuilderConfig(name='x',
                                    factory=factory.BuildFactory(), workername='x')
        self.cfg.load_builders(self.filename,
                               dict(builders=[bldr]))
        self.assertResults(builders=[bldr])

    def test_load_builders_dict(self):
        bldr = dict(name='x', factory=factory.BuildFactory(), workername='x')
        self.cfg.load_builders(self.filename,
                               dict(builders=[bldr]))
        self.assertIsInstance(self.cfg.builders[0], config.BuilderConfig)
        self.assertEqual(self.cfg.builders[0].name, 'x')

    def test_load_builders_abs_builddir(self):
        bldr = dict(name='x', factory=factory.BuildFactory(), workername='x',
                    builddir=os.path.abspath('.'))
        self.cfg.load_builders(self.filename,
                               dict(builders=[bldr]))
        self.assertEqual(
            len(self.flushWarnings([self.cfg.load_builders])),
            1)

    def test_load_workers_defaults(self):
        self.cfg.load_workers(self.filename, {})
        self.assertResults(workers=[])

    def test_load_workers_not_list(self):
        self.cfg.load_workers(self.filename,
                              dict(workers=dict()))
        self.assertConfigError(self.errors, "must be a list")

    def test_load_workers_not_instance(self):
        self.cfg.load_workers(self.filename,
                              dict(workers=[mock.Mock()]))
        self.assertConfigError(self.errors, "must be a list of")

    def test_load_workers_reserved_names(self):
        for name in 'debug', 'change', 'status':
            self.cfg.load_workers(self.filename,
                                  dict(workers=[worker.Worker(name, 'x')]))
            self.assertConfigError(self.errors, "is reserved")
            self.errors.errors[:] = []  # clear out the errors

    def test_load_workers_not_identifiers(self):
        for name in (u"123 no initial digits", u"spaces not allowed",
                     u'a/b', u'\N{SNOWMAN}', u"a.b.c.d", u"a-b_c.d9",):
            self.cfg.load_workers(self.filename,
                                  dict(workers=[worker.Worker(name, 'x')]))
            self.assertConfigError(self.errors, "is not an identifier")
            self.errors.errors[:] = []  # clear out the errors

    def test_load_workers_too_long(self):
        name = u"a" * 51
        self.cfg.load_workers(self.filename,
                              dict(workers=[worker.Worker(name, 'x')]))
        self.assertConfigError(self.errors, "is longer than")
        self.errors.errors[:] = []  # clear out the errors

    def test_load_workers_empty(self):
        name = u""
        self.cfg.load_workers(self.filename,
                              dict(workers=[worker.Worker(name, 'x')]))
        self.errors.errors[:] = self.errors.errors[
            1:2]  # only get necessary error
        self.assertConfigError(self.errors, "cannot be an empty string")
        self.errors.errors[:] = []  # clear out the errors

    def test_load_workers(self):
        wrk = worker.Worker('foo', 'x')
        self.cfg.load_workers(self.filename,
                              dict(workers=[wrk]))
        self.assertResults(workers=[wrk])

    def test_load_workers_old_api(self):
        w = worker.Worker("name", 'x')
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=r"c\['slaves'\] key is deprecated, "
                                r"use c\['workers'\] instead"):
            self.cfg.load_workers(self.filename, dict(slaves=[w]))
        self.assertResults(workers=[w])

    def test_load_workers_new_api(self):
        w = worker.Worker("name", 'x')
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.cfg.load_workers(self.filename, dict(workers=[w]))
        self.assertResults(workers=[w])

    def test_load_workers_old_and_new_api(self):
        w1 = worker.Worker("name1", 'x')
        w2 = worker.Worker("name2", 'x')
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=r"c\['slaves'\] key is deprecated, "
                                r"use c\['workers'\] instead"):
            self.cfg.load_workers(self.filename, dict(slaves=[w1],
                                                      workers=[w2]))

        self.assertConfigError(
            self.errors,
            "Use of c['workers'] and c['slaves'] at the same time "
            "is not supported")
        self.errors.errors[:] = []  # clear out the errors

    def test_load_change_sources_defaults(self):
        self.cfg.load_change_sources(self.filename, {})
        self.assertResults(change_sources=[])

    def test_load_change_sources_not_instance(self):
        self.cfg.load_change_sources(self.filename,
                                     dict(change_source=[mock.Mock()]))
        self.assertConfigError(self.errors, "must be a list of")

    def test_load_change_sources_single(self):
        chsrc = FakeChangeSource()
        self.cfg.load_change_sources(self.filename,
                                     dict(change_source=chsrc))
        self.assertResults(change_sources=[chsrc])

    def test_load_change_sources_list(self):
        chsrc = FakeChangeSource()
        self.cfg.load_change_sources(self.filename,
                                     dict(change_source=[chsrc]))
        self.assertResults(change_sources=[chsrc])

    def test_load_status_not_list(self):
        self.cfg.load_status(self.filename, dict(status="not-list"))
        self.assertConfigError(self.errors, "must be a list of")

    def test_load_status_not_status_rec(self):
        self.cfg.load_status(self.filename, dict(status=['fo']))
        self.assertConfigError(self.errors, "not a status receiver")

    def test_load_user_managers_defaults(self):
        self.cfg.load_user_managers(self.filename, {})
        self.assertResults(user_managers=[])

    def test_load_user_managers_not_list(self):
        self.cfg.load_user_managers(self.filename,
                                    dict(user_managers='foo'))
        self.assertConfigError(self.errors, "must be a list")

    def test_load_user_managers(self):
        um = mock.Mock()
        self.cfg.load_user_managers(self.filename,
                                    dict(user_managers=[um]))
        self.assertResults(user_managers=[um])

    def test_load_www_default(self):
        self.cfg.load_www(self.filename, {})
        self.assertResults(www=dict(port=None,
                                    plugins={}, auth={'name': 'NoAuth'},
                                    authz={},
                                    avatar_methods={'name': 'gravatar'},
                                    logfileName='http.log'))

    def test_load_www_port(self):
        self.cfg.load_www(self.filename,
                          dict(www=dict(port=9888)))
        self.assertResults(www=dict(port=9888,
                                    plugins={}, auth={'name': 'NoAuth'},
                                    authz={},
                                    avatar_methods={'name': 'gravatar'},
                                    logfileName='http.log'))

    def test_load_www_plugin(self):
        self.cfg.load_www(self.filename,
                          dict(www=dict(plugins={'waterfall': {'foo': 'bar'}})))
        self.assertResults(www=dict(port=None,
                                    plugins={'waterfall': {'foo': 'bar'}},
                                    auth={'name': 'NoAuth'},
                                    authz={},
                                    avatar_methods={'name': 'gravatar'},
                                    logfileName='http.log'))

    def test_load_www_allowed_origins(self):
        self.cfg.load_www(self.filename,
                          dict(www=dict(allowed_origins=['a', 'b'])))
        self.assertResults(www=dict(port=None,
                                    allowed_origins=['a', 'b'],
                                    plugins={}, auth={'name': 'NoAuth'},
                                    authz={},
                                    avatar_methods={'name': 'gravatar'},
                                    logfileName='http.log'))

    def test_load_www_logfileName(self):
        self.cfg.load_www(self.filename,
                          dict(www=dict(logfileName='http-access.log')))
        self.assertResults(www=dict(port=None,
                                    plugins={}, auth={'name': 'NoAuth'},
                                    authz={},
                                    avatar_methods={'name': 'gravatar'},
                                    logfileName='http-access.log'))

    def test_load_www_versions(self):
        custom_versions = [
            ('Test Custom Component', '0.0.1'),
            ('Test Custom Component 2', '0.1.0'),
        ]
        self.cfg.load_www(
            self.filename, {'www': dict(versions=custom_versions)})
        self.assertResults(www=dict(port=None,
                                    plugins={}, auth={'name': 'NoAuth'},
                                    authz={},
                                    avatar_methods={'name': 'gravatar'},
                                    versions=custom_versions,
                                    logfileName='http.log'))

    def test_load_www_versions_not_list(self):
        custom_versions = {
            'Test Custom Component': '0.0.1',
            'Test Custom Component 2': '0.0.2',
        }
        self.cfg.load_www(
            self.filename, {'www': dict(versions=custom_versions)})
        self.assertConfigError(
            self.errors, 'Invalid www configuration value of versions')

    def test_load_www_versions_value_invalid(self):
        custom_versions = [('a', '1'), 'abc', ('b',)]
        self.cfg.load_www(
            self.filename, {'www': dict(versions=custom_versions)})
        self.assertConfigError(
            self.errors, 'Invalid www configuration value of versions')

    def test_load_www_cookie_expiration_time_not_timedelta(self):
        self.cfg.load_www(
            self.filename, {'www': dict(cookie_expiration_time=1)})
        self.assertConfigError(
            self.errors, 'Invalid www["cookie_expiration_time"]')

    def test_load_www_unknown(self):
        self.cfg.load_www(self.filename,
                          dict(www=dict(foo="bar")))
        self.assertConfigError(self.errors,
                               "unknown www configuration parameter(s) foo")

    def test_load_services_nominal(self):

        class MyService(service.BuildbotService):

            def reconfigService(foo=None):
                self.foo = foo
        myService = MyService(foo="bar", name="foo")

        self.cfg.load_services(self.filename, dict(
            services=[myService]))
        self.assertResults(services={"foo": myService})

    def test_load_services_badservice(self):

        class MyService(object):
            pass
        myService = MyService()
        self.cfg.load_services(self.filename, dict(
            services=[myService]))
        if PY3:
            errMsg = ("<class 'buildbot.test.unit.test_config."
                      "MasterConfig_loaders.test_load_services_badservice."
                      "<locals>.MyService'> ")
        else:
            errMsg = "<class 'buildbot.test.unit.test_config.MyService'> "
        errMsg += "object should be an instance of buildbot.util.service.BuildbotService"
        self.assertConfigError(self.errors, errMsg)

    def test_load_configurators_norminal(self):

        class MyConfigurator(configurators.ConfiguratorBase):

            def configure(self, config_dict):
                config_dict['foo'] = 'bar'
        c = dict(configurators=[MyConfigurator()])
        self.cfg.run_configurators(self.filename, c)
        self.assertEqual(c['foo'], 'bar')


class MasterConfig_checkers(ConfigErrorsMixin, unittest.TestCase):

    def setUp(self):
        self.cfg = config.MasterConfig()
        self.errors = config.ConfigErrors()
        self.patch(config, '_errors', self.errors)

    # utils

    def setup_basic_attrs(self):
        # set up a basic config for checking; this will be modified below
        sch = mock.Mock()
        sch.name = 'sch'
        sch.listBuilderNames = lambda: ['b1', 'b2']

        b1 = mock.Mock()
        b1.name = 'b1'

        b2 = mock.Mock()
        b2.name = 'b2'

        self.cfg.schedulers = dict(sch=sch)
        self.cfg.workers = [mock.Mock()]
        self.cfg.builders = [b1, b2]

    def setup_builder_locks(self,
                            builder_lock=None,
                            dup_builder_lock=False,
                            bare_builder_lock=False):
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
        def bldr(name):
            b = mock.Mock()
            b.name = name
            b.locks = []
            b.factory.steps = [('cls', (), dict(locks=[]))]
            return b

        def lock(name):
            lock = mock.Mock(spec=locks.MasterLock)
            lock.name = name
            if bare_builder_lock:
                return lock
            return locks.LockAccess(lock, "counting", _skipChecks=True)

        b1, b2 = bldr('b1'), bldr('b2')
        self.cfg.builders = [b1, b2]
        if builder_lock:
            b1.locks.append(lock(builder_lock))
            if dup_builder_lock:
                b2.locks.append(lock(builder_lock))

    # tests

    def test_check_single_master_multimaster(self):
        self.cfg.multiMaster = True
        self.cfg.check_single_master()
        self.assertNoConfigErrors(self.errors)

    def test_check_single_master_no_builders(self):
        self.setup_basic_attrs()
        self.cfg.builders = []
        self.cfg.check_single_master()
        self.assertConfigError(self.errors, "no builders are configured")

    def test_check_single_master_no_workers(self):
        self.setup_basic_attrs()
        self.cfg.workers = []
        self.cfg.check_single_master()
        self.assertConfigError(self.errors, "no workers are configured")

    def test_check_single_master_unsch_builder(self):
        self.setup_basic_attrs()
        b3 = mock.Mock()
        b3.name = 'b3'
        self.cfg.builders.append(b3)
        self.cfg.check_single_master()
        self.assertConfigError(self.errors, "have no schedulers to drive them")

    def test_check_schedulers_unknown_builder(self):
        self.setup_basic_attrs()
        del self.cfg.builders[1]  # remove b2, leaving b1

        self.cfg.check_schedulers()
        self.assertConfigError(self.errors, "Unknown builder 'b2'")

    def test_check_schedulers_ignored_in_multiMaster(self):
        self.setup_basic_attrs()
        del self.cfg.builders[1]  # remove b2, leaving b1
        self.cfg.multiMaster = True
        self.cfg.check_schedulers()
        self.assertNoConfigErrors(self.errors)

    def test_check_schedulers(self):
        self.setup_basic_attrs()
        self.cfg.check_schedulers()
        self.assertNoConfigErrors(self.errors)

    def test_check_locks_dup_builder_lock(self):
        self.setup_builder_locks(builder_lock='l', dup_builder_lock=True)
        self.cfg.check_locks()
        self.assertConfigError(self.errors, "Two locks share")

    def test_check_locks(self):
        self.setup_builder_locks(builder_lock='bl')
        self.cfg.check_locks()
        self.assertNoConfigErrors(self.errors)

    def test_check_locks_none(self):
        # no locks in the whole config, should be fine
        self.setup_builder_locks()
        self.cfg.check_locks()
        self.assertNoConfigErrors(self.errors)

    def test_check_locks_bare(self):
        # check_locks() should be able to handle bare lock object,
        # lock objects that are not wrapped into LockAccess() object
        self.setup_builder_locks(builder_lock='oldlock',
                                 bare_builder_lock=True)
        self.cfg.check_locks()
        self.assertNoConfigErrors(self.errors)

    def test_check_builders_unknown_worker(self):
        wrk = mock.Mock()
        wrk.workername = 'xyz'
        self.cfg.workers = [wrk]

        b1 = FakeBuilder(workernames=['xyz', 'abc'], builddir='x', name='b1')
        self.cfg.builders = [b1]

        self.cfg.check_builders()
        self.assertConfigError(self.errors,
                               "builder 'b1' uses unknown workers 'abc'")

    def test_check_builders_duplicate_name(self):
        b1 = FakeBuilder(workernames=[], name='b1', builddir='1')
        b2 = FakeBuilder(workernames=[], name='b1', builddir='2')
        self.cfg.builders = [b1, b2]

        self.cfg.check_builders()
        self.assertConfigError(self.errors,
                               "duplicate builder name 'b1'")

    def test_check_builders_duplicate_builddir(self):
        b1 = FakeBuilder(workernames=[], name='b1', builddir='dir')
        b2 = FakeBuilder(workernames=[], name='b2', builddir='dir')
        self.cfg.builders = [b1, b2]

        self.cfg.check_builders()
        self.assertConfigError(self.errors,
                               "duplicate builder builddir 'dir'")

    def test_check_builders(self):
        wrk = mock.Mock()
        wrk.workername = 'a'
        self.cfg.workers = [wrk]

        b1 = FakeBuilder(workernames=['a'], name='b1', builddir='dir1')
        b2 = FakeBuilder(workernames=['a'], name='b2', builddir='dir2')
        self.cfg.builders = [b1, b2]

        self.cfg.check_builders()
        self.assertNoConfigErrors(self.errors)

    def test_check_status_fails(self):
        st = FakeStatusReceiver()
        st.checkConfig = lambda status: config.error("oh noes")
        self.cfg.status = [st]

        self.cfg.check_status()

        self.assertConfigError(self.errors, "oh noes")

    def test_check_status(self):
        st = FakeStatusReceiver()
        st.checkConfig = mock.Mock()
        self.cfg.status = [st]

        self.cfg.check_status()

        self.assertNoConfigErrors(self.errors)
        st.checkConfig.assert_called_once_with(self.cfg.status)

    def test_check_ports_protocols_set(self):
        self.cfg.protocols = {"pb": {"port": 10}}
        self.cfg.check_ports()
        self.assertNoConfigErrors(self.errors)

    def test_check_ports_protocols_not_set_workers(self):
        self.cfg.workers = [mock.Mock()]
        self.cfg.check_ports()
        self.assertConfigError(self.errors,
                               "workers are configured, but c['protocols'] not")

    def test_check_ports_protocols_port_duplication(self):
        self.cfg.protocols = {"pb": {"port": 123}, "amp": {"port": 123}}
        self.cfg.check_ports()
        self.assertConfigError(self.errors,
                               "Some of ports in c['protocols'] duplicated")


class MasterConfig_old_worker_api(unittest.TestCase):

    filename = "test.cfg"

    def setUp(self):
        self.cfg = config.MasterConfig()

    def test_worker_old_api(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=r"'slaves' attribute is deprecated, "
                                r"use 'workers' instead"):
            self.assertEqual(self.cfg.slaves, [])

    def test_workers_new_api(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertEqual(self.cfg.workers, [])


class BuilderConfig(ConfigErrorsMixin, unittest.TestCase):

    factory = factory.BuildFactory()

    # utils

    def assertAttributes(self, cfg, **expected):
        got = dict([
            (attr, getattr(cfg, attr))
            for attr, exp in iteritems(expected)])
        self.assertEqual(got, expected)

    # tests

    def test_no_name(self):
        self.assertRaisesConfigError(
            "builder's name is required",
            lambda: config.BuilderConfig(
                factory=self.factory, workernames=['a']))

    def test_reserved_name(self):
        self.assertRaisesConfigError(
            "builder names must not start with an underscore: '_a'",
            lambda: config.BuilderConfig(name='_a',
                                         factory=self.factory, workernames=['a']))

    def test_utf8_name(self):
        self.assertRaisesConfigError(
            "builder names must be unicode or ASCII",
            lambda: config.BuilderConfig(name=u"\N{SNOWMAN}".encode('utf-8'),
                                         factory=self.factory, workernames=['a']))

    def test_no_factory(self):
        self.assertRaisesConfigError(
            "builder 'a' has no factory",
            lambda: config.BuilderConfig(
                name='a', workernames=['a']))

    def test_wrong_type_factory(self):
        self.assertRaisesConfigError(
            "builder 'a's factory is not",
            lambda: config.BuilderConfig(
                factory=[], name='a', workernames=['a']))

    def test_no_workernames(self):
        self.assertRaisesConfigError(
            "builder 'a': at least one workername is required",
            lambda: config.BuilderConfig(
                name='a', factory=self.factory))

    def test_bogus_workernames(self):
        self.assertRaisesConfigError(
            "workernames must be a list or a string",
            lambda: config.BuilderConfig(
                name='a', workernames={1: 2}, factory=self.factory))

    def test_bogus_workername(self):
        self.assertRaisesConfigError(
            "workername must be a string",
            lambda: config.BuilderConfig(
                name='a', workername=1, factory=self.factory))

    def test_bogus_category(self):
        with assertProducesWarning(
                config.ConfigWarning,
                message_pattern=r"builder categories are deprecated and should be replaced with"):
            self.assertRaisesConfigError(
                "category must be a string",
                lambda: config.BuilderConfig(category=13,
                                             name='a', workernames=['a'], factory=self.factory))

    def test_tags_must_be_list(self):
        self.assertRaisesConfigError(
            "tags must be a list",
            lambda: config.BuilderConfig(tags='abc',
                                         name='a', workernames=['a'], factory=self.factory))

    def test_tags_must_be_list_of_str(self):
        self.assertRaisesConfigError(
            "tags list contains something that is not a string",
            lambda: config.BuilderConfig(tags=['abc', 13],
                                         name='a', workernames=['a'], factory=self.factory))

    def test_tags_no_tag_dupes(self):
        self.assertRaisesConfigError(
            "builder 'a': tags list contains duplicate tags: abc",
            lambda: config.BuilderConfig(tags=['abc', 'bca', 'abc'],
                                         name='a', workernames=['a'], factory=self.factory))

    def test_tags_no_categories_too(self):
        self.assertRaisesConfigError(
            "categories are deprecated and replaced by tags; you should only specify tags",
            lambda: config.BuilderConfig(tags=['abc'],
                                         category='def',
                                         name='a', workernames=['a'], factory=self.factory))

    def test_inv_nextWorker(self):
        self.assertRaisesConfigError(
            "nextWorker must be a callable",
            lambda: config.BuilderConfig(nextWorker="foo",
                                         name="a", workernames=['a'], factory=self.factory))

    def test_inv_nextBuild(self):
        self.assertRaisesConfigError(
            "nextBuild must be a callable",
            lambda: config.BuilderConfig(nextBuild="foo",
                                         name="a", workernames=['a'], factory=self.factory))

    def test_inv_canStartBuild(self):
        self.assertRaisesConfigError(
            "canStartBuild must be a callable",
            lambda: config.BuilderConfig(canStartBuild="foo",
                                         name="a", workernames=['a'], factory=self.factory))

    def test_inv_env(self):
        self.assertRaisesConfigError(
            "builder's env must be a dictionary",
            lambda: config.BuilderConfig(env="foo",
                                         name="a", workernames=['a'], factory=self.factory))

    def test_defaults(self):
        cfg = config.BuilderConfig(
            name='a b c', workername='a', factory=self.factory)
        self.assertIdentical(cfg.factory, self.factory)
        self.assertAttributes(cfg,
                              name='a b c',
                              workernames=['a'],
                              builddir='a_b_c',
                              workerbuilddir='a_b_c',
                              tags=[],
                              nextWorker=None,
                              locks=[],
                              env={},
                              properties={},
                              collapseRequests=None,
                              description=None)

    def test_unicode_name(self):
        cfg = config.BuilderConfig(
            name=u'a \N{SNOWMAN} c', workername='a', factory=self.factory)
        self.assertIdentical(cfg.factory, self.factory)
        self.assertAttributes(cfg,
                              name=u'a \N{SNOWMAN} c')

    def test_args(self):
        cfg = config.BuilderConfig(
            name='b', workername='s1', workernames='s2', builddir='bd',
            workerbuilddir='wbd', factory=self.factory, tags=['c'],
            nextWorker=lambda: 'ns', nextBuild=lambda: 'nb', locks=['l'],
            env=dict(x=10), properties=dict(y=20), collapseRequests='cr',
            description='buzz')
        self.assertIdentical(cfg.factory, self.factory)
        self.assertAttributes(cfg,
                              name='b',
                              workernames=['s2', 's1'],
                              builddir='bd',
                              workerbuilddir='wbd',
                              tags=['c'],
                              locks=['l'],
                              env={'x': 10},
                              properties={'y': 20},
                              collapseRequests='cr',
                              description='buzz')

    def test_getConfigDict(self):
        ns = lambda: 'ns'
        nb = lambda: 'nb'
        cfg = config.BuilderConfig(
            name='b', workername='s1', workernames='s2', builddir='bd',
            workerbuilddir='wbd', factory=self.factory, tags=['c'],
            nextWorker=ns, nextBuild=nb, locks=['l'],
            env=dict(x=10), properties=dict(y=20), collapseRequests='cr',
            description='buzz')
        self.assertEqual(cfg.getConfigDict(), {'builddir': 'bd',
                                               'tags': ['c'],
                                               'description': 'buzz',
                                               'env': {'x': 10},
                                               'factory': self.factory,
                                               'locks': ['l'],
                                               'collapseRequests': 'cr',
                                               'name': 'b',
                                               'nextBuild': nb,
                                               'nextWorker': ns,
                                               'properties': {'y': 20},
                                               'workerbuilddir': 'wbd',
                                               'workernames': ['s2', 's1'],
                                               })

    def test_getConfigDict_collapseRequests(self):
        for cr in (False, lambda a, b, c: False):
            cfg = config.BuilderConfig(name='b', collapseRequests=cr,
                                       factory=self.factory, workername='s1')
            self.assertEqual(cfg.getConfigDict(), {'builddir': 'b',
                                                   'collapseRequests': cr,
                                                   'name': 'b',
                                                   'workerbuilddir': 'b',
                                                   'factory': self.factory,
                                                   'workernames': ['s1'],
                                                   })

    def test_init_workername_new_api_no_warns(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            cfg = config.BuilderConfig(
                name='a b c', workername='a', factory=self.factory)

        self.assertEqual(cfg.workernames, ['a'])

    def test_init_workername_old_api_warns(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavename' keyword argument is deprecated"):
            cfg = config.BuilderConfig(
                name='a b c', slavename='a', factory=self.factory)

        self.assertEqual(cfg.workernames, ['a'])

    def test_init_workername_positional(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            cfg = config.BuilderConfig(
                'a b c', 'a', factory=self.factory)

        self.assertEqual(cfg.workernames, ['a'])

    def test_init_workernames_new_api_no_warns(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            cfg = config.BuilderConfig(
                name='a b c', workernames=['a'], factory=self.factory)

        self.assertEqual(cfg.workernames, ['a'])

    def test_init_workernames_old_api_warns(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavenames' keyword argument is deprecated"):
            cfg = config.BuilderConfig(
                name='a b c', slavenames=['a'], factory=self.factory)

        self.assertEqual(cfg.workernames, ['a'])

    def test_init_workernames_positional(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            cfg = config.BuilderConfig(
                'a b c', None, ['a'], factory=self.factory)

        self.assertEqual(cfg.workernames, ['a'])

    def test_workernames_old_api(self):
        cfg = config.BuilderConfig(
            name='a b c', workername='a', factory=self.factory)

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            names_new = cfg.workernames

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavenames' attribute is deprecated"):
            names_old = cfg.slavenames

        self.assertEqual(names_old, ['a'])
        self.assertIdentical(names_new, names_old)

    def test_init_workerbuilddir_new_api_no_warns(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            cfg = config.BuilderConfig(
                name='a b c', workername='a', factory=self.factory,
                workerbuilddir="dir")

        self.assertEqual(cfg.workerbuilddir, 'dir')

    def test_init_workerbuilddir_old_api_warns(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavebuilddir' keyword argument is deprecated"):
            cfg = config.BuilderConfig(
                name='a b c', workername='a', factory=self.factory,
                slavebuilddir='dir')

        self.assertEqual(cfg.workerbuilddir, 'dir')

    def test_init_workerbuilddir_positional(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            cfg = config.BuilderConfig(
                'a b c', 'a', None, None, 'dir', factory=self.factory)

        self.assertEqual(cfg.workerbuilddir, 'dir')

    def test_next_worker_old_api(self):
        f = lambda: None
        cfg = config.BuilderConfig(
            name='a b c', workername='a', factory=self.factory,
            nextWorker=f)

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            new = cfg.nextWorker

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'nextSlave' attribute is deprecated"):
            old = cfg.nextSlave

        self.assertIdentical(old, f)
        self.assertIdentical(new, old)

    def test_init_next_worker_new_api_no_warns(self):
        f = lambda: None
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            cfg = config.BuilderConfig(
                name='a b c', workername='a', factory=self.factory,
                nextWorker=f)

        self.assertEqual(cfg.nextWorker, f)

    def test_init_next_worker_old_api_warns(self):
        f = lambda: None
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'nextSlave' keyword argument is deprecated"):
            cfg = config.BuilderConfig(
                name='a b c', workername='a', factory=self.factory,
                nextSlave=f)

        self.assertEqual(cfg.nextWorker, f)

    def test_init_next_worker_positional(self):
        f = lambda: None
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            cfg = config.BuilderConfig(
                'a b c', 'a', None, None, None, self.factory, None, None, f)

        self.assertEqual(cfg.nextWorker, f)


class FakeService(service.ReconfigurableServiceMixin,
                  service.AsyncService):

    succeed = True
    call_index = 1

    def reconfigServiceWithBuildbotConfig(self, new_config):
        self.called = FakeService.call_index
        FakeService.call_index += 1
        d = service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(
            self, new_config)
        if not self.succeed:
            @d.addCallback
            def fail(_):
                raise ValueError("oh noes")
        return d


class FakeMultiService(service.ReconfigurableServiceMixin,
                       service.AsyncMultiService):

    def reconfigServiceWithBuildbotConfig(self, new_config):
        self.called = True
        d = service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(
            self, new_config)
        return d


class ReconfigurableServiceMixin(unittest.TestCase):

    def test_service(self):
        svc = FakeService()
        d = svc.reconfigServiceWithBuildbotConfig(mock.Mock())

        @d.addCallback
        def check(_):
            self.assertTrue(svc.called)
        return d

    @defer.inlineCallbacks
    def test_service_failure(self):
        svc = FakeService()
        svc.succeed = False
        try:
            yield svc.reconfigServiceWithBuildbotConfig(mock.Mock())
        except ValueError:
            pass
        else:
            self.fail("should have raised ValueError")

    def test_multiservice(self):
        svc = FakeMultiService()
        ch1 = FakeService()
        ch1.setServiceParent(svc)
        ch2 = FakeMultiService()
        ch2.setServiceParent(svc)
        ch3 = FakeService()
        ch3.setServiceParent(ch2)
        d = svc.reconfigServiceWithBuildbotConfig(mock.Mock())

        @d.addCallback
        def check(_):
            self.assertTrue(svc.called)
            self.assertTrue(ch1.called)
            self.assertTrue(ch2.called)
            self.assertTrue(ch3.called)
        return d

    def test_multiservice_priority(self):
        parent = FakeMultiService()
        svc128 = FakeService()
        svc128.setServiceParent(parent)

        services = [svc128]
        for i in range(20, 1, -1):
            svc = FakeService()
            svc.reconfig_priority = i
            svc.setServiceParent(parent)
            services.append(svc)

        d = parent.reconfigServiceWithBuildbotConfig(mock.Mock())

        @d.addCallback
        def check(_):
            prio_order = [svc.called for svc in services]
            called_order = sorted(prio_order)
            self.assertEqual(prio_order, called_order)
        return d

    @defer.inlineCallbacks
    def test_multiservice_nested_failure(self):
        svc = FakeMultiService()
        ch1 = FakeService()
        ch1.setServiceParent(svc)
        ch1.succeed = False
        try:
            yield svc.reconfigServiceWithBuildbotConfig(mock.Mock())
        except ValueError:
            pass
        else:
            self.fail("should have raised ValueError")

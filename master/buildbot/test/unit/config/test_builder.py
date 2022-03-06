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


from twisted.trial import unittest

from buildbot.config.builder import BuilderConfig
from buildbot.process import factory
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.warnings import DeprecatedApiWarning


class BuilderConfigTests(ConfigErrorsMixin, unittest.TestCase):

    factory = factory.BuildFactory()

    # utils

    def assertAttributes(self, cfg, **expected):
        got = {
            attr: getattr(cfg, attr)
            for attr, exp in expected.items()}
        self.assertEqual(got, expected)

    # tests

    def test_no_name(self):
        with self.assertRaisesConfigError("builder's name is required"):
            BuilderConfig(factory=self.factory, workernames=['a'])

    def test_reserved_name(self):
        with self.assertRaisesConfigError(
                "builder names must not start with an underscore: '_a'"):
            BuilderConfig(name='_a', factory=self.factory, workernames=['a'])

    def test_utf8_name(self):
        with self.assertRaisesConfigError(
                "builder names must be unicode or ASCII"):
            BuilderConfig(name="\N{SNOWMAN}".encode('utf-8'),
                          factory=self.factory, workernames=['a'])

    def test_no_factory(self):
        with self.assertRaisesConfigError("builder 'a' has no factory"):
            BuilderConfig(name='a', workernames=['a'])

    def test_wrong_type_factory(self):
        with self.assertRaisesConfigError("builder 'a's factory is not"):
            BuilderConfig(factory=[], name='a', workernames=['a'])

    def test_no_workernames(self):
        with self.assertRaisesConfigError(
                "builder 'a': at least one workername is required"):
            BuilderConfig(name='a', factory=self.factory)

    def test_bogus_workernames(self):
        with self.assertRaisesConfigError(
                "workernames must be a list or a string"):
            BuilderConfig(name='a', workernames={1: 2}, factory=self.factory)

    def test_bogus_workername(self):
        with self.assertRaisesConfigError("workername must be a string"):
            BuilderConfig(name='a', workername=1, factory=self.factory)

    def test_tags_must_be_list(self):
        with self.assertRaisesConfigError("tags must be a list"):
            BuilderConfig(tags='abc', name='a', workernames=['a'], factory=self.factory)

    def test_tags_must_be_list_of_str(self):
        with self.assertRaisesConfigError(
                "tags list contains something that is not a string"):
            BuilderConfig(tags=['abc', 13], name='a', workernames=['a'], factory=self.factory)

    def test_tags_no_tag_dupes(self):
        with self.assertRaisesConfigError(
                "builder 'a': tags list contains duplicate tags: abc"):
            BuilderConfig(tags=['abc', 'bca', 'abc'], name='a', workernames=['a'],
                          factory=self.factory)

    def test_inv_nextWorker(self):
        with self.assertRaisesConfigError("nextWorker must be a callable"):
            BuilderConfig(nextWorker="foo", name="a", workernames=['a'], factory=self.factory)

    def test_inv_nextBuild(self):
        with self.assertRaisesConfigError("nextBuild must be a callable"):
            BuilderConfig(nextBuild="foo", name="a", workernames=['a'], factory=self.factory)

    def test_inv_canStartBuild(self):
        with self.assertRaisesConfigError("canStartBuild must be a callable"):
            BuilderConfig(canStartBuild="foo", name="a", workernames=['a'], factory=self.factory)

    def test_inv_env(self):
        with self.assertRaisesConfigError("builder's env must be a dictionary"):
            BuilderConfig(env="foo", name="a", workernames=['a'], factory=self.factory)

    def test_defaults(self):
        cfg = BuilderConfig(name='a b c', workername='a', factory=self.factory)
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
        cfg = BuilderConfig(name='a \N{SNOWMAN} c', workername='a', factory=self.factory)
        self.assertIdentical(cfg.factory, self.factory)
        self.assertAttributes(cfg,
                              name='a \N{SNOWMAN} c')

    def test_args(self):
        cfg = BuilderConfig(name='b', workername='s1', workernames='s2', builddir='bd',
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

    def test_too_long_property(self):
        with self.assertRaisesConfigError("exceeds maximum length of"):
            BuilderConfig(name="a", workernames=['a'], factory=self.factory,
                          properties={'a' * 257: 'value'})

    def test_too_long_default_property(self):
        with self.assertRaisesConfigError("exceeds maximum length of"):
            BuilderConfig(name="a", workernames=['a'], factory=self.factory,
                          defaultProperties={'a' * 257: 'value'})

    def test_getConfigDict(self):
        ns = lambda: 'ns'
        nb = lambda: 'nb'
        cfg = BuilderConfig(name='b', workername='s1', workernames='s2', builddir='bd',
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
            cfg = BuilderConfig(name='b', collapseRequests=cr,
                                factory=self.factory, workername='s1')
            self.assertEqual(cfg.getConfigDict(), {'builddir': 'b',
                                                   'collapseRequests': cr,
                                                   'name': 'b',
                                                   'workerbuilddir': 'b',
                                                   'factory': self.factory,
                                                   'workernames': ['s1'],
                                                   })

    def test_init_workername_keyword(self):
        cfg = BuilderConfig(name='a b c', workername='a', factory=self.factory)
        self.assertEqual(cfg.workernames, ['a'])

    def test_init_workername_positional(self):
        with assertNotProducesWarnings(DeprecatedApiWarning):
            cfg = BuilderConfig('a b c', 'a', factory=self.factory)

        self.assertEqual(cfg.workernames, ['a'])

    def test_init_workernames_keyword(self):
        cfg = BuilderConfig(name='a b c', workernames=['a'], factory=self.factory)

        self.assertEqual(cfg.workernames, ['a'])

    def test_init_workernames_positional(self):
        with assertNotProducesWarnings(DeprecatedApiWarning):
            cfg = BuilderConfig('a b c', None, ['a'], factory=self.factory)

        self.assertEqual(cfg.workernames, ['a'])

    def test_init_workerbuilddir_keyword(self):
        cfg = BuilderConfig(name='a b c', workername='a', factory=self.factory,
                            workerbuilddir="dir")

        self.assertEqual(cfg.workerbuilddir, 'dir')

    def test_init_workerbuilddir_positional(self):
        with assertNotProducesWarnings(DeprecatedApiWarning):
            cfg = BuilderConfig('a b c', 'a', None, None, 'dir', factory=self.factory)

        self.assertEqual(cfg.workerbuilddir, 'dir')

    def test_init_next_worker_keyword(self):
        f = lambda: None
        cfg = BuilderConfig(name='a b c', workername='a', factory=self.factory, nextWorker=f)
        self.assertEqual(cfg.nextWorker, f)

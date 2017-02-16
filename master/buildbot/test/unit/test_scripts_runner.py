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

from __future__ import absolute_import
from __future__ import print_function

import getpass
import os
import sys

import mock

from twisted.python import log
from twisted.python import runtime
from twisted.python import usage
from twisted.python.compat import NativeStringIO
from twisted.trial import unittest

from buildbot.scripts import base
from buildbot.scripts import runner
from buildbot.test.util import misc


class OptionsMixin(object):

    def setUpOptions(self):
        self.options_file = {}
        self.patch(base.SubcommandOptions, 'loadOptionsFile',
                   lambda other_self: self.options_file)

    def assertOptions(self, opts, exp):
        got = dict([(k, opts[k]) for k in exp])
        if got != exp:
            msg = []
            for k in exp:
                if opts[k] != exp[k]:
                    msg.append(" %s: expected %r, got %r" %
                               (k, exp[k], opts[k]))
            self.fail("did not get expected options\n" + ("\n".join(msg)))


class TestUpgradeMasterOptions(OptionsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpOptions()

    def parse(self, *args):
        self.opts = runner.UpgradeMasterOptions()
        self.opts.parseOptions(args)
        return self.opts

    def test_synopsis(self):
        opts = runner.UpgradeMasterOptions()
        self.assertIn('buildbot upgrade-master', opts.getSynopsis())

    def test_defaults(self):
        opts = self.parse()
        exp = dict(quiet=False, replace=False)
        self.assertOptions(opts, exp)

    def test_short(self):
        opts = self.parse('-q', '-r')
        exp = dict(quiet=True, replace=True)
        self.assertOptions(opts, exp)

    def test_long(self):
        opts = self.parse('--quiet', '--replace')
        exp = dict(quiet=True, replace=True)
        self.assertOptions(opts, exp)


class TestCreateMasterOptions(OptionsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpOptions()

    def parse(self, *args):
        self.opts = runner.CreateMasterOptions()
        self.opts.parseOptions(args)
        return self.opts

    def defaults_and(self, **kwargs):
        defaults = dict(force=False, relocatable=False, config='master.cfg',
                        db='sqlite:///state.sqlite', basedir=os.getcwd(), quiet=False,
                        **{'no-logrotate': False, 'log-size': 10000000,
                           'log-count': 10})
        unk_keys = set(kwargs.keys()) - set(defaults.keys())
        assert not unk_keys, "invalid keys %s" % (unk_keys,)
        opts = defaults.copy()
        opts.update(kwargs)
        return opts

    def test_synopsis(self):
        opts = runner.CreateMasterOptions()
        self.assertIn('buildbot create-master', opts.getSynopsis())

    def test_defaults(self):
        opts = self.parse()
        exp = self.defaults_and()
        self.assertOptions(opts, exp)

    def test_db_quiet(self):
        opts = self.parse('-q')
        exp = self.defaults_and(quiet=True)
        self.assertOptions(opts, exp)

    def test_db_quiet_long(self):
        opts = self.parse('--quiet')
        exp = self.defaults_and(quiet=True)
        self.assertOptions(opts, exp)

    def test_force(self):
        opts = self.parse('-f')
        exp = self.defaults_and(force=True)
        self.assertOptions(opts, exp)

    def test_force_long(self):
        opts = self.parse('--force')
        exp = self.defaults_and(force=True)
        self.assertOptions(opts, exp)

    def test_relocatable(self):
        opts = self.parse('-r')
        exp = self.defaults_and(relocatable=True)
        self.assertOptions(opts, exp)

    def test_relocatable_long(self):
        opts = self.parse('--relocatable')
        exp = self.defaults_and(relocatable=True)
        self.assertOptions(opts, exp)

    def test_no_logrotate(self):
        opts = self.parse('-n')
        exp = self.defaults_and(**{'no-logrotate': True})
        self.assertOptions(opts, exp)

    def test_no_logrotate_long(self):
        opts = self.parse('--no-logrotate')
        exp = self.defaults_and(**{'no-logrotate': True})
        self.assertOptions(opts, exp)

    def test_config(self):
        opts = self.parse('-cxyz')
        exp = self.defaults_and(config='xyz')
        self.assertOptions(opts, exp)

    def test_config_long(self):
        opts = self.parse('--config=xyz')
        exp = self.defaults_and(config='xyz')
        self.assertOptions(opts, exp)

    def test_log_size(self):
        opts = self.parse('-s124')
        exp = self.defaults_and(**{'log-size': 124})
        self.assertOptions(opts, exp)

    def test_log_size_long(self):
        opts = self.parse('--log-size=124')
        exp = self.defaults_and(**{'log-size': 124})
        self.assertOptions(opts, exp)

    def test_log_size_noninteger(self):
        self.assertRaises(usage.UsageError,
                          lambda: self.parse('--log-size=1M'))

    def test_log_count(self):
        opts = self.parse('-l124')
        exp = self.defaults_and(**{'log-count': 124})
        self.assertOptions(opts, exp)

    def test_log_count_long(self):
        opts = self.parse('--log-count=124')
        exp = self.defaults_and(**{'log-count': 124})
        self.assertOptions(opts, exp)

    def test_log_count_none(self):
        opts = self.parse('--log-count=None')
        exp = self.defaults_and(**{'log-count': None})
        self.assertOptions(opts, exp)

    def test_log_count_noninteger(self):
        self.assertRaises(usage.UsageError,
                          lambda: self.parse('--log-count=M'))

    def test_db_long(self):
        opts = self.parse('--db=foo://bar')
        exp = self.defaults_and(db='foo://bar')
        self.assertOptions(opts, exp)

    def test_db_invalid(self):
        self.assertRaisesRegex(usage.UsageError,
                               "could not parse database URL 'inv_db_url'",
                               self.parse, "--db=inv_db_url")

    def test_db_basedir(self):
        path = r'c:\foo\bar' if runtime.platformType == "win32" else '/foo/bar'
        opts = self.parse('-f', path)
        exp = self.defaults_and(force=True, basedir=path)
        self.assertOptions(opts, exp)


class BaseTestSimpleOptions(OptionsMixin):
    # tests for options with just --quiet and a usage message

    commandName = None
    optionsClass = None

    def setUp(self):
        self.setUpOptions()

    def parse(self, *args):
        self.opts = self.optionsClass()
        self.opts.parseOptions(args)
        return self.opts

    def test_synopsis(self):
        opts = self.optionsClass()
        self.assertIn('buildbot %s' % self.commandName, opts.getSynopsis())

    def test_defaults(self):
        opts = self.parse()
        exp = dict(quiet=False)
        self.assertOptions(opts, exp)

    def test_quiet(self):
        opts = self.parse('--quiet')
        exp = dict(quiet=True)
        self.assertOptions(opts, exp)


class TestStopOptions(BaseTestSimpleOptions, unittest.TestCase):
    commandName = 'stop'
    optionsClass = runner.StopOptions


class TestResetartOptions(BaseTestSimpleOptions, unittest.TestCase):
    commandName = 'restart'
    optionsClass = runner.RestartOptions

    def test_nodaemon(self):
        opts = self.parse('--nodaemon')
        exp = dict(nodaemon=True)
        self.assertOptions(opts, exp)


class TestStartOptions(BaseTestSimpleOptions, unittest.TestCase):
    commandName = 'start'
    optionsClass = runner.StartOptions

    def test_nodaemon(self):
        opts = self.parse('--nodaemon')
        exp = dict(nodaemon=True)
        self.assertOptions(opts, exp)


class TestReconfigOptions(BaseTestSimpleOptions, unittest.TestCase):
    commandName = 'reconfig'
    optionsClass = runner.ReconfigOptions


class TestTryOptions(OptionsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpOptions()

    def parse(self, *args):
        self.opts = runner.TryOptions()
        self.opts.parseOptions(args)
        return self.opts

    def defaults_and(self, **kwargs):
        defaults = dict(connect=None, host=None, jobdir=None, username=None,
                        master=None, passwd=None, who=None, comment=None, diff=None,
                        patchlevel=0, baserev=None, vc=None, branch=None,
                        repository=None, topfile=None, topdir=None, wait=False,
                        dryrun=False, quiet=False, builders=[], properties={},
                        buildbotbin='buildbot')
        # dashes make python syntax hard..
        defaults['get-builder-names'] = False
        if 'get_builder_names' in kwargs:
            kwargs['get-builder-names'] = kwargs['get_builder_names']
            del kwargs['get_builder_names']
        assert set(kwargs.keys()) <= set(defaults.keys()), "invalid keys"
        opts = defaults.copy()
        opts.update(kwargs)
        return opts

    def test_synopsis(self):
        opts = runner.TryOptions()
        self.assertIn('buildbot try', opts.getSynopsis())

    def test_defaults(self):
        opts = self.parse()
        exp = self.defaults_and()
        self.assertOptions(opts, exp)

    def test_properties(self):
        opts = self.parse('--properties=a=b')
        exp = self.defaults_and(properties=dict(a='b'))
        self.assertOptions(opts, exp)

    def test_properties_multiple_opts(self):
        opts = self.parse('--properties=X=1', '--properties=Y=2')
        exp = self.defaults_and(properties=dict(X='1', Y='2'))
        self.assertOptions(opts, exp)

    def test_properties_equals(self):
        opts = self.parse('--properties=X=2+2=4')
        exp = self.defaults_and(properties=dict(X='2+2=4'))
        self.assertOptions(opts, exp)

    def test_properties_commas(self):
        opts = self.parse('--properties=a=b,c=d')
        exp = self.defaults_and(properties=dict(a='b', c='d'))
        self.assertOptions(opts, exp)

    def test_property(self):
        opts = self.parse('--property=a=b')
        exp = self.defaults_and(properties=dict(a='b'))
        self.assertOptions(opts, exp)

    def test_property_multiple_opts(self):
        opts = self.parse('--property=X=1', '--property=Y=2')
        exp = self.defaults_and(properties=dict(X='1', Y='2'))
        self.assertOptions(opts, exp)

    def test_property_equals(self):
        opts = self.parse('--property=X=2+2=4')
        exp = self.defaults_and(properties=dict(X='2+2=4'))
        self.assertOptions(opts, exp)

    def test_property_commas(self):
        opts = self.parse('--property=a=b,c=d')
        exp = self.defaults_and(properties=dict(a='b,c=d'))
        self.assertOptions(opts, exp)

    def test_property_and_properties(self):
        opts = self.parse('--property=X=1', '--properties=Y=2')
        exp = self.defaults_and(properties=dict(X='1', Y='2'))
        self.assertOptions(opts, exp)

    def test_properties_builders_multiple(self):
        opts = self.parse('--builder=aa', '--builder=bb')
        exp = self.defaults_and(builders=['aa', 'bb'])
        self.assertOptions(opts, exp)

    def test_options_short(self):
        opts = self.parse(
            *'-n -q -c pb -u me -m mr:7 -w you -C comm -p 2 -b bb'.split())
        exp = self.defaults_and(dryrun=True, quiet=True, connect='pb',
                                username='me', master='mr:7', who='you', comment='comm',
                                patchlevel=2, builders=['bb'])
        self.assertOptions(opts, exp)

    def test_options_long(self):
        opts = self.parse(
            *"""--wait --dryrun --get-builder-names --quiet --connect=pb
                --host=h --jobdir=j --username=u --master=m:1234 --passwd=p
                --who=w --comment=comm --diff=d --patchlevel=7 --baserev=br
                --vc=cvs --branch=br --repository=rep --builder=bl
                --properties=a=b --topfile=Makefile --topdir=.
                --buildbotbin=.virtualenvs/buildbot/bin/buildbot""".split())
        exp = self.defaults_and(wait=True, dryrun=True, get_builder_names=True,
                                quiet=True, connect='pb', host='h', jobdir='j', username='u',
                                master='m:1234', passwd='p', who='w', comment='comm', diff='d',
                                patchlevel=7, baserev='br', vc='cvs', branch='br',
                                repository='rep', builders=['bl'], properties=dict(a='b'),
                                topfile='Makefile', topdir='.',
                                buildbotbin='.virtualenvs/buildbot/bin/buildbot')
        self.assertOptions(opts, exp)

    def test_patchlevel_inval(self):
        self.assertRaises(ValueError, lambda:
                          self.parse('-p', 'a'))

    def test_config_builders(self):
        self.options_file['try_builders'] = ['a', 'b']
        opts = self.parse()
        self.assertOptions(opts, dict(builders=['a', 'b']))

    def test_config_builders_override(self):
        self.options_file['try_builders'] = ['a', 'b']
        opts = self.parse('-b', 'd')  # overrides a, b
        self.assertOptions(opts, dict(builders=['d']))

    def test_config_old_names(self):
        self.options_file['try_masterstatus'] = 'ms'
        self.options_file['try_dir'] = 'td'
        self.options_file['try_password'] = 'pw'
        opts = self.parse()
        self.assertOptions(opts, dict(master='ms', jobdir='td', passwd='pw'))

    def test_config_masterstatus(self):
        self.options_file['masterstatus'] = 'ms'
        opts = self.parse()
        self.assertOptions(opts, dict(master='ms'))

    def test_config_masterstatus_override(self):
        self.options_file['masterstatus'] = 'ms'
        opts = self.parse('-m', 'mm')
        self.assertOptions(opts, dict(master='mm'))

    def test_config_options(self):
        self.options_file.update(dict(try_connect='pb', try_vc='cvs',
                                      try_branch='br', try_repository='rep', try_topdir='.',
                                      try_topfile='Makefile', try_host='h', try_username='u',
                                      try_jobdir='j', try_password='p', try_master='m:8', try_who='w',
                                      try_comment='comm', try_quiet='y', try_wait='y',
                                      try_buildbotbin='.virtualenvs/buildbot/bin/buildbot'))
        opts = self.parse()
        exp = self.defaults_and(wait=True, quiet=True, connect='pb', host='h',
                                jobdir='j', username='u', master='m:8', passwd='p', who='w',
                                comment='comm', vc='cvs', branch='br', repository='rep',
                                topfile='Makefile', topdir='.',
                                buildbotbin='.virtualenvs/buildbot/bin/buildbot')
        self.assertOptions(opts, exp)

    def test_pb_withNoMaster(self):
        """
        When 'builbot try' is asked to connect via pb, but no master is
        specified, a usage error is raised.
        """
        self.assertRaises(usage.UsageError, self.parse, '--connect=pb')

    def test_pb_withInvalidMaster(self):
        """
        When 'buildbot try' is asked to connect via pb, but an invalid
        master is specified, a usage error is raised.
        """
        self.assertRaises(usage.UsageError, self.parse,
                          '--connect=pb', '--master=foo')


class TestSendChangeOptions(OptionsMixin, unittest.TestCase):

    master_and_who = ['-m', 'm:1', '-W', 'w']

    def setUp(self):
        self.setUpOptions()
        self.getpass_response = 'typed-password'
        self.patch(getpass, 'getpass', lambda prompt: self.getpass_response)

    def parse(self, *args):
        self.opts = runner.SendChangeOptions()
        self.opts.parseOptions(args)
        return self.opts

    def test_synopsis(self):
        opts = runner.SendChangeOptions()
        self.assertIn('buildbot sendchange', opts.getSynopsis())

    def test_defaults(self):
        opts = self.parse('-m', 'm:1', '-W', 'me')
        exp = dict(master='m:1', auth=('change', 'changepw'), who='me',
                   vc=None, repository='', project='', branch=None, category=None,
                   revision=None, revision_file=None, property=None,
                   comments='', logfile=None, when=None, revlink='',
                   encoding='utf8', files=())
        self.assertOptions(opts, exp)

    def test_files(self):
        opts = self.parse(*self.master_and_who + ['a', 'b', 'c'])
        self.assertEqual(opts['files'], ('a', 'b', 'c'))

    def test_properties(self):
        opts = self.parse('--property', 'x:y', '--property', 'a:b',
                          *self.master_and_who)
        self.assertEqual(opts['properties'], dict(x="y", a="b"))

    def test_properties_with_colon(self):
        opts = self.parse('--property', 'x:http://foo', *self.master_and_who)
        self.assertEqual(opts['properties'], dict(x='http://foo'))

    def test_config_file(self):
        self.options_file['master'] = 'MMM:123'
        self.options_file['who'] = 'WWW'
        self.options_file['branch'] = 'BBB'
        self.options_file['category'] = 'CCC'
        self.options_file['vc'] = 'svn'
        opts = self.parse()
        exp = dict(master='MMM:123', who='WWW',
                   branch='BBB', category='CCC', vc='svn')
        self.assertOptions(opts, exp)

    def test_short_args(self):
        opts = self.parse(*('-m m:1 -a a:b -W W -R r -P p -b b -s git ' +
                            '-C c -r r -p pn:pv -c c -F f -w 123 -l l -e e').split())
        exp = dict(master='m:1', auth=('a', 'b'), who='W', repository='r',
                   project='p', branch='b', category='c', revision='r', vc='git',
                   properties=dict(pn='pv'), comments='c', logfile='f',
                   when=123.0, revlink='l', encoding='e')
        self.assertOptions(opts, exp)

    def test_long_args(self):
        opts = self.parse(*('--master m:1 --auth a:b --who w --repository r ' +
                            '--project p --branch b --category c --revision r --vc git ' +
                            '--property pn:pv --comments c --logfile f ' +
                            '--when 123 --revlink l --encoding e').split())
        exp = dict(master='m:1', auth=('a', 'b'), who='w', repository='r',
                   project='p', branch='b', category='c', revision='r', vc='git',
                   properties=dict(pn='pv'), comments='c', logfile='f',
                   when=123.0, revlink='l', encoding='e')
        self.assertOptions(opts, exp)

    def test_revision_file(self):
        with open('revfile', 'wt') as f:
            f.write('my-rev')
        self.addCleanup(lambda: os.unlink('revfile'))
        opts = self.parse('--revision_file', 'revfile', *self.master_and_who)
        self.assertOptions(opts, dict(revision='my-rev'))

    def test_invalid_when(self):
        self.assertRaises(usage.UsageError,
                          lambda: self.parse('--when=foo', *self.master_and_who))

    def test_comments_overrides_logfile(self):
        opts = self.parse('--logfile', 'logs', '--comments', 'foo',
                          *self.master_and_who)
        self.assertOptions(opts, dict(comments='foo'))

    def test_logfile(self):
        with open('comments', 'wt') as f:
            f.write('hi')
        self.addCleanup(lambda: os.unlink('comments'))
        opts = self.parse('--logfile', 'comments', *self.master_and_who)
        self.assertOptions(opts, dict(comments='hi'))

    def test_logfile_stdin(self):
        stdin = mock.Mock()
        stdin.read = lambda: 'hi'
        self.patch(sys, 'stdin', stdin)
        opts = self.parse('--logfile', '-', *self.master_and_who)
        self.assertOptions(opts, dict(comments='hi'))

    def test_auth_getpass(self):
        opts = self.parse('--auth=dustin', *self.master_and_who)
        self.assertOptions(opts, dict(auth=('dustin', 'typed-password')))

    def test_invalid_vcs(self):
        self.assertRaises(usage.UsageError,
                          lambda: self.parse('--vc=foo', *self.master_and_who))

    def test_invalid_master(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          "--who=test", "-m foo")


class TestTryServerOptions(OptionsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpOptions()

    def parse(self, *args):
        self.opts = runner.TryServerOptions()
        self.opts.parseOptions(args)
        return self.opts

    def test_synopsis(self):
        opts = runner.TryServerOptions()
        self.assertIn('buildbot tryserver', opts.getSynopsis())

    def test_defaults(self):
        self.assertRaises(usage.UsageError,
                          lambda: self.parse())

    def test_with_jobdir(self):
        opts = self.parse('--jobdir', 'xyz')
        exp = dict(jobdir='xyz')
        self.assertOptions(opts, exp)


class TestCheckConfigOptions(OptionsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpOptions()

    def parse(self, *args):
        self.opts = runner.CheckConfigOptions()
        self.opts.parseOptions(args)
        return self.opts

    def test_synopsis(self):
        opts = runner.CheckConfigOptions()
        self.assertIn('buildbot checkconfig', opts.getSynopsis())

    def test_defaults(self):
        opts = self.parse()
        exp = dict(quiet=False)
        self.assertOptions(opts, exp)

    def test_configfile(self):
        opts = self.parse('foo.cfg')
        exp = dict(quiet=False, configFile='foo.cfg')
        self.assertOptions(opts, exp)

    def test_quiet(self):
        opts = self.parse('-q')
        exp = dict(quiet=True)
        self.assertOptions(opts, exp)


class TestUserOptions(OptionsMixin, unittest.TestCase):

    # mandatory arguments
    extra_args = ['--master', 'a:1',
                  '--username', 'u', '--passwd', 'p']

    def setUp(self):
        self.setUpOptions()

    def parse(self, *args):
        self.opts = runner.UserOptions()
        self.opts.parseOptions(args)
        return self.opts

    def test_defaults(self):
        self.assertRaises(usage.UsageError,
                          lambda: self.parse())

    def test_synopsis(self):
        opts = runner.UserOptions()
        self.assertIn('buildbot user', opts.getSynopsis())

    def test_master(self):
        opts = self.parse("--master", "abcd:1234",
                          '--op=get', '--ids=x', '--username=u', '--passwd=p')
        self.assertOptions(opts, dict(master="abcd:1234"))

    def test_ids(self):
        opts = self.parse("--ids", "id1,id2,id3",
                          '--op', 'get', *self.extra_args)
        self.assertEqual(opts['ids'], ['id1', 'id2', 'id3'])

    def test_info(self):
        opts = self.parse("--info", "git=Tyler Durden <tyler@mayhem.net>",
                          '--op', 'add', *self.extra_args)
        self.assertEqual(opts['info'],
                         [dict(git='Tyler Durden <tyler@mayhem.net>')])

    def test_info_only_id(self):
        opts = self.parse("--info", "tdurden",
                          '--op', 'update', *self.extra_args)
        self.assertEqual(opts['info'], [dict(identifier='tdurden')])

    def test_info_with_id(self):
        opts = self.parse("--info", "tdurden:svn=marla",
                          '--op', 'update', *self.extra_args)
        self.assertEqual(
            opts['info'], [dict(identifier='tdurden', svn='marla')])

    def test_info_multiple(self):
        opts = self.parse("--info", "git=Tyler Durden <tyler@mayhem.net>",
                          "--info", "git=Narrator <narrator@mayhem.net>",
                          '--op', 'add', *self.extra_args)
        self.assertEqual(opts['info'],
                         [dict(git='Tyler Durden <tyler@mayhem.net>'),
                          dict(git='Narrator <narrator@mayhem.net>')])

    def test_config_user_params(self):
        self.options_file['user_master'] = 'mm:99'
        self.options_file['user_username'] = 'un'
        self.options_file['user_passwd'] = 'pw'
        opts = self.parse('--op', 'get', '--ids', 'x')
        self.assertOptions(
            opts, dict(master='mm:99', username='un', passwd='pw'))

    def test_config_master(self):
        self.options_file['master'] = 'mm:99'
        opts = self.parse('--op', 'get', '--ids', 'x',
                          '--username=u', '--passwd=p')
        self.assertOptions(opts, dict(master='mm:99'))

    def test_config_master_override(self):
        self.options_file['master'] = 'not seen'
        self.options_file['user_master'] = 'mm:99'
        opts = self.parse('--op', 'get', '--ids', 'x',
                          '--username=u', '--passwd=p')
        self.assertOptions(opts, dict(master='mm:99'))

    def test_invalid_info(self):
        self.assertRaises(usage.UsageError,
                          lambda: self.parse("--info", "foo=bar",
                                             '--op', 'add', *self.extra_args))

    def test_no_master(self):
        self.assertRaises(usage.UsageError,
                          lambda: self.parse('-op=foo'))

    def test_invalid_master(self):
        self.assertRaises(usage.UsageError, self.parse, '-m', 'foo')

    def test_no_operation(self):
        self.assertRaises(usage.UsageError, self.parse, '-m', 'a:1')

    def test_bad_operation(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          '-m', 'a:1', '--op=mayhem')

    def test_no_username(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          '-m', 'a:1', '--op=add')

    def test_no_password(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          '--op=add', '-m', 'a:1', '-u', 'tdurden')

    def test_invalid_bb_username(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          '--op=add', '--bb_username=tdurden',
                          *self.extra_args)

    def test_invalid_bb_password(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          '--op=add', '--bb_password=marla',
                          *self.extra_args)

    def test_update_no_bb_username(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          '--op=update', '--bb_password=marla',
                          *self.extra_args)

    def test_update_no_bb_password(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          '--op=update', '--bb_username=tdurden',
                          *self.extra_args)

    def test_no_ids_info(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          '--op=add', *self.extra_args)

    def test_ids_with_add(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          '--op=add', '--ids=id1', *self.extra_args)

    def test_ids_with_update(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          '--op=update', '--ids=id1', *self.extra_args)

    def test_no_ids_found_update(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          "--op=update", "--info=svn=x", *self.extra_args)

    def test_id_with_add(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          "--op=add", "--info=id:x", *self.extra_args)

    def test_info_with_remove(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          '--op=remove', '--info=x=v', *self.extra_args)

    def test_info_with_get(self):
        self.assertRaises(usage.UsageError,
                          self.parse,
                          '--op=get', '--info=x=v', *self.extra_args)


class TestOptions(OptionsMixin, misc.StdoutAssertionsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpOptions()
        self.setUpStdoutAssertions()

    def parse(self, *args):
        self.opts = runner.Options()
        self.opts.parseOptions(args)
        return self.opts

    def test_defaults(self):
        self.assertRaises(usage.UsageError,
                          lambda: self.parse())

    def test_version(self):
        try:
            self.parse('--version')
        except SystemExit as e:
            self.assertEqual(e.args[0], 0)
        self.assertInStdout('Buildbot version:')

    def test_verbose(self):
        self.patch(log, 'startLogging', mock.Mock())
        self.assertRaises(usage.UsageError, self.parse, "--verbose")
        log.startLogging.assert_called_once_with(sys.stderr)


class TestRun(unittest.TestCase):

    class MySubCommand(usage.Options):
        subcommandFunction = 'buildbot.test.unit.test_scripts_runner.subcommandFunction'
        optFlags = [
            ['loud', 'l', 'be noisy']
        ]

        def postOptions(self):
            if self['loud']:
                raise usage.UsageError('THIS IS ME BEING LOUD')

    def setUp(self):
        # patch our subcommand in
        self.patch(runner.Options, 'subCommands',
                   [['my', None, self.MySubCommand, 'my, my']])

        # and patch in the callback for it
        global subcommandFunction
        subcommandFunction = mock.Mock(name='subcommandFunction',
                                       return_value=3)

    def test_run_good(self):
        self.patch(sys, 'argv', ['buildbot', 'my'])
        try:
            runner.run()
        except SystemExit as e:
            self.assertEqual(e.args[0], 3)
        else:
            self.fail("didn't exit")

    def test_run_bad(self):
        self.patch(sys, 'argv', ['buildbot', 'my', '-l'])
        stdout = NativeStringIO()
        self.patch(sys, 'stdout', stdout)
        try:
            runner.run()
        except SystemExit as e:
            self.assertEqual(e.args[0], 1)
        else:
            self.fail("didn't exit")
        self.assertIn('THIS IS ME', stdout.getvalue())

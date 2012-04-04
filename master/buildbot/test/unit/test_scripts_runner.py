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
import cStringIO
import getpass
import mock
from twisted.trial import unittest
from twisted.python import usage
from twisted.internet import defer, reactor
from buildbot.scripts import base, runner, checkconfig
from buildbot.clients import sendchange

class OptionsMixin(object):

    def setUpOptions(self):
        self.options_file = {}
        self.patch(base.SubcommandOptions, 'loadOptionsFile',
                lambda other_self : self.options_file)

    def assertOptions(self, opts, exp):
        got = dict([(k, opts[k]) for k in exp])
        if got != exp:
            msg = []
            for k in exp:
                if opts[k] != exp[k]:
                    msg.append(" %s: expected %r, got %r" %
                               (k, exp[k], opts[k]))
            self.fail("did not get expected options\n" + ("\n".join(msg)))

class TestSendChangeOptions(OptionsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpOptions()

    def parse(self, *args):
        self.opts = runner.SendChangeOptions()
        self.opts.parseOptions(args)
        return self.opts

    def test_synopsis(self):
        opts = runner.SendChangeOptions()
        self.assertIn('buildbot sendchange', opts.getSynopsis())

    def test_defaults(self):
        opts = self.parse()
        exp = dict(master=None, auth=None, who=None, vc=None,
                repository='', project='', branch=None, category=None,
                revision=None, revision_file=None, property=None,
                comments=None, logfile=None, when=None, revlink='',
                encoding='utf8', files=())
        self.assertOptions(opts, exp)

    def test_files(self):
        opts = self.parse('a', 'b', 'c')
        self.assertEqual(opts['files'], ('a', 'b', 'c'))

    def test_properties(self):
        opts = self.parse('--property', 'x:y', '--property', 'a:b')
        self.assertEqual(opts['properties'], dict(x="y", a="b"))

    def test_properties_with_colon(self):
        opts = self.parse('--property', 'x:http://foo')
        self.assertEquals(opts['properties'], dict(x='http://foo'))

    def test_config_file(self):
        self.options_file['master'] = 'MMM'
        self.options_file['who'] = 'WWW'
        self.options_file['branch'] = 'BBB'
        self.options_file['category'] = 'CCC'
        opts = self.parse()
        exp = dict(master='MMM', who='WWW',
                branch='BBB', category='CCC')
        self.assertOptions(opts, exp)

    def test_short_args(self):
        opts = self.parse(*('-m m -a a -W w -R r -P p -b b -s s ' +
            '-C c -r r -p pn:pv -c c -F f -w w -l l -e e').split())
        exp = dict(master='m', auth='a', who='w', repository='r', project='p',
                branch='b', category='c', revision='r', vc='s',
                properties=dict(pn='pv'), comments='c', logfile='f', when='w',
                revlink='l', encoding='e')
        self.assertOptions(opts, exp)

    def test_long_args(self):
        opts = self.parse(*('--master m --auth a --who w --repository r ' +
            '--project p --branch b --category c --revision r --vc s ' +
            '--revision_file rr --property pn:pv --comments c --logfile f ' +
            '--when w --revlink l --encoding e').split())
        exp = dict(master='m', auth='a', who='w', repository='r', project='p',
                branch='b', category='c', revision='r', vc='s', revision_file='rr',
                properties=dict(pn='pv'), comments='c', logfile='f', when='w',
                revlink='l', encoding='e')
        self.assertOptions(opts, exp)

class TestSendChange(unittest.TestCase):

    class FakeSender:
        def __init__(self, master, auth, encoding=None):
            self.master = master
            self.auth = auth
            self.encoding = encoding
            self.fail = False

        def send(self, branch, revision, comments, files, **kwargs):
            kwargs['branch'] = branch
            kwargs['revision'] = revision
            kwargs['comments'] = comments
            kwargs['files'] = files
            self.send_kwargs = kwargs
            d = defer.Deferred()
            if self.fail:
                reactor.callLater(0, d.errback, RuntimeError("oh noes"))
            else:
                reactor.callLater(0, d.callback, None)
            return d

    def setUp(self):
        def Sender_constr(*args, **kwargs):
            self.sender = self.FakeSender(*args, **kwargs)
            return self.sender
        self.patch(sendchange, 'Sender', Sender_constr)

        self.stdout = cStringIO.StringIO()
        self.patch(sys, 'stdout', self.stdout)

    def test_sendchange_defaults(self):
        d = runner.sendchange(dict(who='me', master='a:1'))
        def check(_):
            # called correctly
            self.assertEqual((self.sender.master, self.sender.auth,
                    self.sender.encoding, self.sender.send_kwargs),
                    ('a:1', ['change','changepw'], 'utf8', {
                        'branch': None,
                        'category': None,
                        'comments': '',
                        'files': (),
                        'project': '',
                        'properties': {},
                        'repository': '',
                        'revision': None,
                        'revlink': '',
                        'when': None,
                        'who': 'me',
                        'vc': None}))
            # nothing to stdout
            self.assertEqual(self.stdout.getvalue(), '')
        d.addCallback(check)
        return d

    def test_sendchange_args(self):
        d = runner.sendchange(dict(encoding='utf16', who='me', auth='a:b',
                master='a:1', branch='br', category='cat', revision='rr',
                properties={'a':'b'}, repository='rep', project='prj', vc='git',
                revlink='rl', when='1234', comments='comm', files=('a', 'b')))
        def check(_):
            self.assertEqual((self.sender.master, self.sender.auth,
                    self.sender.encoding, self.sender.send_kwargs),
                    ('a:1', ['a','b'], 'utf16', {
                        'branch': 'br',
                        'category': 'cat',
                        'comments': 'comm',
                        'files': ('a', 'b'),
                        'project': 'prj',
                        'properties': {'a':'b'},
                        'repository': 'rep',
                        'revision': 'rr',
                        'revlink': 'rl',
                        'when': 1234.0,
                        'who': 'me',
                        'vc': 'git'}))
            self.assertEqual(self.stdout.getvalue(), '')
        d.addCallback(check)
        return d

    def test_sendchange_revision_file(self):
        with open('rf', 'w') as f:
            f.write('abcd')
        d = runner.sendchange(dict(who='me', master='a:1', revision_file='rf'))
        def check(_):
            self.assertEqual((self.sender.master, self.sender.auth,
                    self.sender.encoding, self.sender.send_kwargs['revision']),
                    ('a:1', ['change','changepw'], 'utf8', 'abcd'))
            self.assertEqual(self.stdout.getvalue(), '')
            try:
                os.unlink('rf')
            except:
                pass
        d.addCallback(check)
        return d

    def test_sendchange_logfile(self):
        with open('lf', 'w') as f:
            f.write('hello')
        d = runner.sendchange(dict(who='me', master='a:1', logfile='lf'))
        def check(_):
            self.assertEqual((self.sender.master, self.sender.auth,
                    self.sender.encoding, self.sender.send_kwargs['comments']),
                    ('a:1', ['change','changepw'], 'utf8', 'hello'))
            self.assertEqual(self.stdout.getvalue(), '')
            try:
                os.unlink('lf')
            except:
                pass
        d.addCallback(check)
        return d

    def test_sendchange_logfile_stdin(self):
        stdin = mock.Mock()
        stdin.read = lambda : 'hi!'
        self.patch(sys, 'stdin', stdin)
        d = runner.sendchange(dict(who='me', master='a:1', logfile='-'))
        def check(_):
            self.assertEqual((self.sender.master, self.sender.auth,
                    self.sender.encoding, self.sender.send_kwargs['comments']),
                    ('a:1', ['change','changepw'], 'utf8', 'hi!'))
            self.assertEqual(self.stdout.getvalue(), '')
            try:
                os.unlink('lf')
            except:
                pass
        d.addCallback(check)
        return d

    def test_sendchange_bad_vc(self):
        d = defer.maybeDeferred(lambda :
                runner.sendchange(dict(master='a:1', who="abc", vc="blargh")))
        return self.assertFailure(d, AssertionError)

    def test_sendchange_auth_prompt(self):
        self.patch(getpass, 'getpass', lambda prompt : 'sekrit')
        d = runner.sendchange(dict(who='me', master='a:1', auth='user'))
        def check(_):
            self.assertEqual((self.sender.master, self.sender.auth,
                    self.sender.encoding),
                    ('a:1', ['user','sekrit'], 'utf8'))
            self.assertEqual(self.stdout.getvalue(), '')
        d.addCallback(check)
        return d

    def test_sendchange_who_required(self):
        d = defer.maybeDeferred(lambda :
                runner.sendchange(dict(master='a:1')))
        return self.assertFailure(d, AssertionError)

    def test_sendchange_master_required(self):
        d = defer.maybeDeferred(lambda :
                runner.sendchange(dict(who='abc')))
        return self.assertFailure(d, AssertionError)

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
        exp = dict(quiet=False, configFile='master.cfg')
        self.assertOptions(opts, exp)

    def test_configfile(self):
        opts = self.parse('foo.cfg')
        exp = dict(quiet=False, configFile='foo.cfg')
        self.assertOptions(opts, exp)

    def test_quiet(self):
        opts = self.parse('-q')
        exp = dict(quiet=True, configFile='master.cfg')
        self.assertOptions(opts, exp)

class TestCheckConfig(unittest.TestCase):

    class FakeConfigLoader(object):
        testcase = None
        def __init__(self, **kwargs):
            self.testcase.ConfigLoader_kwargs = kwargs

        def load(self, quiet=False):
            self.testcase.config_loaded = True
            self.testcase.load_quiet = quiet
            return self.testcase.load_return_value

    def setUp(self):
        self.patch(checkconfig, 'ConfigLoader',
                        self.FakeConfigLoader)
        self.FakeConfigLoader.testcase = self
        self.load_return_value = True
        self.config_loaded = False
        self.load_quiet = False
        self.ConfigLoader_kwargs = None

    def test_doCheckConfig(self):
        self.load_return_value = True
        res = runner.doCheckConfig(dict(configFile='master.cfg', quiet=False))
        self.assertTrue(res)
        self.assertTrue(self.config_loaded)
        self.assertFalse(self.load_quiet)
        self.assertEqual(self.ConfigLoader_kwargs,
                dict(configFileName='master.cfg'))

    def test_doCheckConfig_quiet(self):
        res = runner.doCheckConfig(dict(configFile='master.cfg', quiet=True))
        self.assertTrue(res)
        self.assertTrue(self.config_loaded)
        self.assertTrue(self.load_quiet)
        self.assertEqual(self.ConfigLoader_kwargs,
                dict(configFileName='master.cfg'))

    def test_doCheckConfig_dir(self):
        os.mkdir('checkconfig_dir')
        res = runner.doCheckConfig(dict(configFile='checkconfig_dir',
                                      quiet=False))
        self.assertTrue(res)
        self.assertTrue(self.config_loaded)
        self.assertEqual(self.ConfigLoader_kwargs,
                dict(basedir='checkconfig_dir'))

    def test_doCheckConfig_bad_file(self):
        self.load_return_value = False
        res = runner.doCheckConfig(dict(configFile='master.cfg', quiet=False))
        self.assertFalse(res)
        self.assertTrue(self.config_loaded)


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

    def test_properties_builders_multiple(self):
        opts = self.parse('--builder=aa', '--builder=bb')
        exp = self.defaults_and(builders=['aa', 'bb'])
        self.assertOptions(opts, exp)

    def test_options_short(self):
        opts = self.parse(
                *'-n -q -c pb -u me -m mstr -w you -C comm -p 2 -b bb'.split())
        exp = self.defaults_and(dryrun=True, quiet=True, connect='pb',
                username='me', master='mstr', who='you', comment='comm',
                patchlevel=2, builders=['bb'])
        self.assertOptions(opts, exp)

    def test_options_long(self):
        opts = self.parse(
                *"""--wait --dryrun --get-builder-names --quiet --connect=pb
                --host=h --jobdir=j --username=u --master=m --passwd=p
                --who=w --comment=comm --diff=d --patchlevel=7 --baserev=br
                --vc=cvs --branch=br --repository=rep --builder=bl
                --properties=a=b --topfile=Makefile --topdir=.
                --buildbotbin=.virtualenvs/buildbot/bin/buildbot""".split())
        exp = self.defaults_and(wait=True, dryrun=True, get_builder_names=True,
                quiet=True, connect='pb', host='h', jobdir='j', username='u',
                master='m', passwd='p', who='w', comment='comm', diff='d',
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
        opts = self.parse('-b', 'd') # overrides a, b
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
            try_jobdir='j', try_password='p', try_master='m', try_who='w',
            try_comment='comm', try_quiet='y', try_wait='y',
            try_buildbotbin='.virtualenvs/buildbot/bin/buildbot'))
        opts = self.parse()
        exp = self.defaults_and(wait=True, quiet=True, connect='pb', host='h',
                jobdir='j', username='u', master='m', passwd='p', who='w',
                comment='comm', vc='cvs', branch='br', repository='rep',
                topfile='Makefile', topdir='.',
                buildbotbin='.virtualenvs/buildbot/bin/buildbot')
        self.assertOptions(opts, exp)

class TestUserOptions(OptionsMixin, unittest.TestCase):

    # mandatory arguments
    extra_args = [ '--master', 'a:1',
                   '--username', 'u', '--passwd', 'p' ]

    def setUp(self):
        self.setUpOptions()

    def parse(self, *args):
        self.opts = runner.UserOptions()
        self.opts.parseOptions(args)
        return self.opts

    def test_defaults(self):
        self.assertRaises(usage.UsageError,
                lambda : self.parse())

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
        self.assertEqual(opts['info'], [dict(identifier='tdurden', svn='marla')])

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
        self.assertOptions(opts, dict(master='mm:99', username='un', passwd='pw'))

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
                lambda : self.parse("--info", "foo=bar",
                          '--op', 'add', *self.extra_args))

    def test_no_master(self):
        self.assertRaises(usage.UsageError,
            lambda : self.parse('-op=foo'))

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
                **{'no-logrotate':False, 'log-size':'10000000',
                   'log-count':'10'})
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
        exp = self.defaults_and(**{'no-logrotate' : True})
        self.assertOptions(opts, exp)

    def test_no_logrotate_long(self):
        opts = self.parse('--no-logrotate')
        exp = self.defaults_and(**{'no-logrotate' : True})
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
        exp = self.defaults_and(**{'log-size':'124'})
        self.assertOptions(opts, exp)

    def test_log_size_long(self):
        opts = self.parse('--log-size=124')
        exp = self.defaults_and(**{'log-size':'124'})
        self.assertOptions(opts, exp)

    def test_log_size_noninteger(self):
        self.assertRaises(usage.UsageError,
            lambda :self.parse('--log-size=1M'))

    def test_log_count(self):
        opts = self.parse('-l124')
        exp = self.defaults_and(**{'log-count':'124'})
        self.assertOptions(opts, exp)

    def test_log_count_long(self):
        opts = self.parse('--log-count=124')
        exp = self.defaults_and(**{'log-count':'124'})
        self.assertOptions(opts, exp)

    def test_log_count_noninteger(self):
        self.assertRaises(usage.UsageError,
            lambda :self.parse('--log-count=M'))

    def test_db_long(self):
        opts = self.parse('--db=foo://bar')
        exp = self.defaults_and(db='foo://bar')
        self.assertOptions(opts, exp)

    def test_db_basedir(self):
        opts = self.parse('-f', '/foo/bar')
        exp = self.defaults_and(force=True, basedir='/foo/bar')
        self.assertOptions(opts, exp)

class TestDebugClientOptions(OptionsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpOptions()

    def parse(self, *args):
        self.opts = runner.DebugClientOptions()
        self.opts.parseOptions(args)
        return self.opts

    def test_synopsis(self):
        opts = runner.DebugClientOptions()
        self.assertIn('buildbot debugclient', opts.getSynopsis())

    def test_defaults(self):
        self.assertRaises(usage.UsageError,
                lambda : self.parse())

    def test_args_missing_passwd(self):
        self.assertRaises(usage.UsageError,
                lambda : self.parse('-m', 'mm'))

    def test_options_long(self):
        opts = self.parse('--master', 'mm', '--passwd', 'pp')
        exp = dict(master='mm', passwd='pp')
        self.assertOptions(opts, exp)

    def test_positional_master_passwd(self):
        opts = self.parse('foo', 'pass')
        exp = dict(master='foo', passwd='pass')
        self.assertOptions(opts, exp)

    def test_positional_master(self):
        opts = self.parse('-p', 'pass', 'foo')
        exp = dict(master='foo', passwd='pass')
        self.assertOptions(opts, exp)

    def test_args_master_passwd(self):
        opts = self.parse('foo', 'pass')
        exp = dict(master='foo', passwd='pass')
        self.assertOptions(opts, exp)

    def test_missing_both(self):
        self.assertRaises(usage.UsageError,
            lambda :self.parse())

    def test_missing_passwd(self):
        self.assertRaises(usage.UsageError,
            lambda :self.parse('master'))

    def test_missing_master(self):
        self.assertRaises(usage.UsageError,
            lambda :self.parse('-p', 'pass'))

    def test_options_extra_positional(self):
        self.assertRaises(usage.UsageError,
                lambda : self.parse('mm', 'pp', '??'))

    def test_options_master(self):
        self.options_file['master'] = 'opt'
        opts = self.parse('-p', 'pass')
        exp = dict(master='opt', passwd='pass')
        self.assertOptions(opts, exp)

    def test_options_debugMaster(self):
        self.options_file['master'] = 'not seen'
        self.options_file['debugMaster'] = 'opt'
        opts = self.parse('-p', 'pass')
        exp = dict(master='opt', passwd='pass')
        self.assertOptions(opts, exp)


class TestBaseStatusClientOptions(OptionsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpOptions()

    def parse(self, *args):
        self.opts = runner.BaseStatusClientOptions()
        self.opts.parseOptions(args)
        return self.opts

    def test_defaults(self):
        opts = self.parse('--master', 'm')
        exp = dict(master='m', username='statusClient', passwd='clientpw')
        self.assertOptions(opts, exp)

    def test_short(self):
        opts = self.parse('-m', 'm', '-u', 'u', '-p', 'p')
        exp = dict(master='m', username='u', passwd='p')
        self.assertOptions(opts, exp)

    def test_long(self):
        opts = self.parse('--master', 'm', '--username', 'u', '--passwd', 'p')
        exp = dict(master='m', username='u', passwd='p')
        self.assertOptions(opts, exp)

    def test_positional_master(self):
        opts = self.parse('--username', 'u', '--passwd', 'p', 'm')
        exp = dict(master='m', username='u', passwd='p')
        self.assertOptions(opts, exp)

    def test_positional_extra(self):
        self.assertRaises(usage.UsageError,
            lambda : self.parse('--username', 'u', '--passwd', 'p', 'm', '2'))

    def test_missing_master(self):
        self.assertRaises(usage.UsageError,
            lambda : self.parse('--username', 'u', '--passwd', 'p'))

    def test_options_masterstatus(self):
        self.options_file['master'] = 'not seen'
        self.options_file['masterstatus'] = 'opt'
        opts = self.parse('-p', 'pass', '-u', 'user')
        exp = dict(master='opt', username='user', passwd='pass')
        self.assertOptions(opts, exp)


class TestStatusLogOptions(unittest.TestCase):

    def test_synopsis(self):
        opts = runner.StatusLogOptions()
        self.assertIn('buildbot statuslog', opts.getSynopsis())


class TestStatusGuiOptions(unittest.TestCase):

    def test_synopsis(self):
        opts = runner.StatusGuiOptions()
        self.assertIn('buildbot statusgui', opts.getSynopsis())


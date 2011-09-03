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
import sys
import cStringIO
import getpass
import mock
from twisted.trial import unittest
from twisted.internet import defer, reactor
from buildbot.scripts import runner, checkconfig
from buildbot.clients import sendchange, usersclient
from buildbot.process.users import users

class OptionsMixin(object):

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
        self.options_file = {}
        self.patch(runner, 'loadOptionsFile', lambda : self.options_file)

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

    def test_sendchange_deprecated_username(self):
        d = runner.sendchange(dict(username='me', master='a:1'))
        def check(_):
            self.assertEqual((self.sender.master, self.sender.auth,
                    self.sender.encoding, self.sender.send_kwargs['who']),
                    ('a:1', ['change','changepw'], 'utf8', 'me'))
            self.assertIn('is deprecated', self.stdout.getvalue())
        d.addCallback(check)
        return d

    def test_sendchange_revision_file(self):
        open('rf', 'w').write('abcd')
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
        open('lf', 'w').write('hello')
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
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

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
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_sendchange_master_required(self):
        d = defer.maybeDeferred(lambda :
                runner.sendchange(dict(who='abc')))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

class TestCheckConfigOptions(OptionsMixin, unittest.TestCase):

    def setUp(self):
        self.options_file = {}
        self.patch(runner, 'loadOptionsFile', lambda : self.options_file)

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

        def load(self):
            self.testcase.config_loaded = True
            if self.testcase.load_exception:
                return defer.fail(ValueError('I feel undervalued'))
            else:
                return defer.succeed(None)

    def setUp(self):
        # temporarily remove the @in_reactor decoration
        self.patch(runner, 'doCheckConfig', runner.doCheckConfig._orig)

        self.patch(checkconfig, 'ConfigLoader',
                        self.FakeConfigLoader)
        self.FakeConfigLoader.testcase = self
        self.load_exception = False
        self.config_loaded = False
        self.ConfigLoader_kwargs = None

        self.stdout = cStringIO.StringIO()
        self.patch(sys, 'stdout', self.stdout)

    def test_doCheckConfig(self):
        d = runner.doCheckConfig(dict(configFile='master.cfg', quiet=False))
        def check(res):
            self.assertTrue(self.config_loaded)
            self.assertTrue(res)
            self.assertEqual(self.ConfigLoader_kwargs,
                    dict(configFileName='master.cfg'))
            self.assertEqual(self.stdout.getvalue().strip(),
                             "Config file is good!")
        d.addCallback(check)
        return d

    def test_doCheckConfig_quiet(self):
        d = runner.doCheckConfig(dict(configFile='master.cfg', quiet=True))
        def check(res):
            self.assertTrue(self.config_loaded)
            self.assertTrue(res)
            self.assertEqual(self.ConfigLoader_kwargs,
                    dict(configFileName='master.cfg'))
            self.assertEqual(self.stdout.getvalue().strip(), "")
        d.addCallback(check)
        return d

    def test_doCheckConfig_dir(self):
        os.mkdir('checkconfig_dir')
        d = runner.doCheckConfig(dict(configFile='checkconfig_dir',
                                      quiet=False))
        def check(res):
            self.assertTrue(self.config_loaded)
            self.assertTrue(res)
            self.assertEqual(self.ConfigLoader_kwargs,
                    dict(basedir='checkconfig_dir'))
            self.assertEqual(self.stdout.getvalue().strip(),
                             "Config file is good!")
        d.addCallback(check)
        return d

    def test_doCheckConfig_exception(self):
        self.load_exception = True
        d = runner.doCheckConfig(dict(configFile='master.cfg', quiet=False))
        def check(res):
            self.assertTrue(self.config_loaded)
            self.assertFalse(res)
            # (exception gets logged..)
        d.addCallback(check)
        return d

class TestTryOptions(OptionsMixin, unittest.TestCase):

    def setUp(self):
        self.options_file = {}
        self.patch(runner, 'loadOptionsFile', lambda : self.options_file)

    def parse(self, *args):
        self.opts = runner.TryOptions()
        self.opts.parseOptions(args)
        return self.opts

    def defaults_and(self, **kwargs):
        defaults = dict(connect=None, host=None, jobdir=None, username=None,
                master=None, passwd=None, who=None, comment=None, diff=None,
                patchlevel=0, baserev=None, vc=None, branch=None,
                repository=None, topfile=None, topdir=None, wait=False,
                dryrun=False, quiet=False, builders=[], properties={})
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
                --properties=a=b --topfile=Makefile --topdir=.""".split())
        exp = self.defaults_and(wait=True, dryrun=True, get_builder_names=True,
                quiet=True, connect='pb', host='h', jobdir='j', username='u',
                master='m', passwd='p', who='w', comment='comm', diff='d',
                patchlevel=7, baserev='br', vc='cvs', branch='br',
                repository='rep', builders=['bl'], properties=dict(a='b'),
                topfile='Makefile', topdir='.')
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
            try_comment='comm', try_quiet='y', try_wait='y'))
        opts = self.parse()
        exp = self.defaults_and(wait=True, quiet=True, connect='pb', host='h',
                jobdir='j', username='u', master='m', passwd='p', who='w',
                comment='comm', vc='cvs', branch='br', repository='rep',
                topfile='Makefile', topdir='.')
        self.assertOptions(opts, exp)

class TestUserOptions(OptionsMixin, unittest.TestCase):

    def setUp(self):
        self.options_file = {}
        self.patch(runner, 'loadOptionsFile', lambda : self.options_file)

    def parse(self, *args):
        self.opts = runner.UserOptions()
        self.opts.parseOptions(args)
        return self.opts

    def test_defaults(self):
        opts = self.parse()
        exp = dict(master=None, username=None, passwd=None, op=None,
                   bb_username=None, bb_password=None, ids=[], info=[])
        self.assertOptions(opts, exp)

    def test_synopsis(self):
        opts = runner.UserOptions()
        self.assertIn('buildbot user', opts.getSynopsis())

    def test_master(self):
        opts = self.parse("--master", "abcd")
        self.assertOptions(opts, dict(master="abcd"))

    def test_ids(self):
        opts = self.parse("--ids", "id1,id2,id3")
        self.assertEqual(opts['ids'], ['id1', 'id2', 'id3'])

    def test_info(self):
        opts = self.parse("--info", "git=Tyler Durden <tyler@mayhem.net>")
        self.assertEqual(opts['info'],
                         [dict(git='Tyler Durden <tyler@mayhem.net>')])

    def test_info_only_id(self):
        opts = self.parse("--info", "tdurden")
        self.assertEqual(opts['info'], [dict(identifier='tdurden')])

    def test_info_with_id(self):
        opts = self.parse("--info", "tdurden:svn=marla")
        self.assertEqual(opts['info'], [dict(identifier='tdurden', svn='marla')])

    def test_info_multiple(self):
        opts = self.parse("--info", "git=Tyler Durden <tyler@mayhem.net>",
                          "--info", "git=Narrator <narrator@mayhem.net>")
        self.assertEqual(opts['info'],
                         [dict(git='Tyler Durden <tyler@mayhem.net>'),
                          dict(git='Narrator <narrator@mayhem.net>')])

    def test_config_user_params(self):
        self.options_file['user_master'] = 'mm:99'
        self.options_file['user_username'] = 'un'
        self.options_file['user_passwd'] = 'pw'
        opts = self.parse()
        self.assertOptions(opts, dict(master='mm:99', username='un', passwd='pw'))

    def test_config_master(self):
        self.options_file['master'] = 'mm:99'
        opts = self.parse()
        self.assertOptions(opts, dict(master='mm:99'))

    def test_config_master_override(self):
        self.options_file['master'] = 'not seen'
        self.options_file['user_master'] = 'mm:99'
        opts = self.parse()
        self.assertOptions(opts, dict(master='mm:99'))


class TestUsersClient(OptionsMixin, unittest.TestCase):

    class FakeUsersClient(object):
        def __init__(self, master, username="user", passwd="userpw", port=0):
            self.master = master
            self.port = port
            self.username = username
            self.passwd = passwd
            self.fail = False

        def send(self, op, bb_username, bb_password, ids, info):
            self.op = op
            self.bb_username = bb_username
            self.bb_password = bb_password
            self.ids = ids
            self.info = info
            d = defer.Deferred()
            if self.fail:
                reactor.callLater(0, d.errback, RuntimeError("oh noes"))
            else:
                reactor.callLater(0, d.callback, None)
            return d

    def setUp(self):
        def fake_UsersClient(*args):
            self.usersclient = self.FakeUsersClient(*args)
            return self.usersclient
        self.patch(usersclient, 'UsersClient', fake_UsersClient)

    def test_usersclient_no_master(self):
        d = defer.maybeDeferred(lambda :
                                    runner.users_client(dict(op='add')))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_no_port(self):
        d = defer.maybeDeferred(lambda :
                                    runner.users_client(dict(master='a',
                                                             op='add')))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_no_op(self):
        d = defer.maybeDeferred(lambda :
                                    runner.users_client(dict(master='a:9990')))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_no_username_password(self):
        d = defer.maybeDeferred(lambda :
                                    runner.users_client(dict(master='a:9990',
                                                             op='add')))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_bad_op(self):
        d = defer.maybeDeferred(lambda :
                    runner.users_client(dict(master='a:9990', username="x",
                                             passwd="y", op='edit')))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_just_bb_username(self):
        d = defer.maybeDeferred(lambda :
                    runner.users_client(dict(master='a:9990', username="x",
                                             passwd="y", bb_username='buddy',
                                             op='update')))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_bb_not_update(self):
        d = defer.maybeDeferred(lambda :
                    runner.users_client(dict(master='a:9990', username="x",
                                             passwd="y", bb_username='buddy',
                                             bb_password='hey', op='add')))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_no_ids_no_info(self):
        d = defer.maybeDeferred(lambda :
                     runner.users_client(dict(master='a:9990', username="x",
                                              passwd="y", op='add')))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_ids_and_info(self):
        d = defer.maybeDeferred(lambda :
                    runner.users_client(dict(master='a:9990', username="x",
                                              passwd="y", op='add', ids=['me'],
                                              info=[{'full_name':'b'}])))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_add_and_ids(self):
        d = defer.maybeDeferred(lambda :
                    runner.users_client(dict(master='a:9990', username="x",
                                              passwd="y", op='add', ids=['me'],
                                              info=None)))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_update_and_ids(self):
        d = defer.maybeDeferred(lambda :
                    runner.users_client(dict(master='a:9990', username="x",
                                              passwd="y", op='update', ids=['me'],
                                              info=None)))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_remove_get_and_info(self):
        d = defer.maybeDeferred(lambda :
                    runner.users_client(dict(master='a:9990', username="x",
                                              passwd="y", op='remove', ids=None,
                                              info=[{'email':'x'}])))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(AssertionError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_update_no_identifier(self):
        d = defer.maybeDeferred(lambda :
                    runner.users_client(dict(master='a:9990', username="x",
                                              passwd="y", op='update', ids=None,
                                              info=[{'email':'x'}])))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(ValueError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_add_existing_identifier(self):
        d = defer.maybeDeferred(lambda :
                    runner.users_client(dict(master='a:9990', username="x",
                                              passwd="y", op='add', ids=None,
                                              info=[{'identifier':'x'}])))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(ValueError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_bad_attr_type(self):
        d = defer.maybeDeferred(lambda :
                    runner.users_client(dict(master='a:9990', username="x",
                                              passwd="y", op='add', ids=None,
                                              info=[{'b':'y'}])))
        def cb(_):
            self.fail("shouldn't succeed")
        def eb(f):
            f.trap(ValueError)
            pass # A-OK
        d.addCallbacks(cb, eb)
        return d

    def test_usersclient_send_ids(self):
        d = runner.users_client(dict(master='a:9990', username="x",
                                     passwd="y", op='get', bb_username=None,
                                     bb_password=None, ids=['me', 'you'],
                                     info=None))
        def check(_):
            c = self.usersclient
            self.assertEqual((c.master, c.port, c.username, c.passwd, c.op,
                              c.ids, c.info),
                             ('a', 9990, "x", "y", 'get', ['me', 'you'], None))
        d.addCallback(check)
        return d

    def test_usersclient_send_update_info(self):
        encrypted = users.encrypt("day")
        def _fake_encrypt(passwd):
            return encrypted
        self.patch(users, 'encrypt', _fake_encrypt)

        d = runner.users_client(dict(master='a:9990', username="x",
                                     passwd="y", op='update', bb_username='bud',
                                     bb_password='day', ids=None,
                                     info=[{'identifier':'x', 'svn':'x'}]))
        def check(_):
            c = self.usersclient
            self.assertEqual((c.master, c.port, c.username, c.passwd, c.op,
                              c.bb_username, c.bb_password, c.ids, c.info),
                             ('a', 9990, "x", "y", 'update', 'bud', encrypted,
                              None, [{'identifier':'x', 'svn':'x'}]))
        d.addCallback(check)
        return d

    def test_usersclient_send_add_info(self):
        d = runner.users_client(dict(master='a:9990', username="x",
                                     passwd="y", op='add', bb_username=None,
                                     bb_password=None, ids=None,
                                     info=[{'git':'x <h@c>'}]))
        def check(_):
            c = self.usersclient
            self.assertEqual((c.master, c.port, c.username, c.passwd, c.op,
                              c.bb_username, c.bb_password, c.ids, c.info),
                             ('a', 9990, "x", "y", 'add', None, None, None,
                              [{'identifier':'x <h@c>','git': 'x <h@c>'}]))
        d.addCallback(check)
        return d

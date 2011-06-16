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
from buildbot.scripts import runner
from buildbot.clients import sendchange

class TestSendChangeOptions(unittest.TestCase):

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
        exp = dict(master=None, auth=None, who=None,
                repository='', project='', branch=None, category=None,
                revision=None, revision_file=None, property=None,
                comments=None, logfile=None, when=None, revlink='',
                encoding='utf8', files=())
        self.assertEqual(dict([(k, opts[k]) for k in exp]), exp)

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
        self.assertEqual(dict([(k, opts[k]) for k in exp]), exp)

    def test_short_args(self):
        opts = self.parse(*('-m m -a a -W w -R r -P p -b b ' +
            '-C c -r r -p pn:pv -c c -F f -w w -l l -e e').split())
        exp = dict(master='m', auth='a', who='w', repository='r', project='p',
                branch='b', category='c', revision='r',
                properties=dict(pn='pv'), comments='c', logfile='f', when='w',
                revlink='l', encoding='e')
        self.assertEqual(dict([(k, opts[k]) for k in exp]), exp)

    def test_long_args(self):
        opts = self.parse(*('--master m --auth a --who w --repository r ' +
            '--project p --branch b --category c --revision r ' +
            '--revision_file rr --property pn:pv --comments c --logfile f ' +
            '--when w --revlink l --encoding e').split())
        exp = dict(master='m', auth='a', who='w', repository='r', project='p',
                branch='b', category='c', revision='r', revision_file='rr',
                properties=dict(pn='pv'), comments='c', logfile='f', when='w',
                revlink='l', encoding='e')
        self.assertEqual(dict([(k, opts[k]) for k in exp]), exp)

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
                        'who': 'me'}))
            # nothing to stdout
            self.assertEqual(self.stdout.getvalue(), '')
        d.addCallback(check)
        return d

    def test_sendchange_args(self):
        d = runner.sendchange(dict(encoding='utf16', who='me', auth='a:b',
                master='a:1', branch='br', category='cat', revision='rr',
                properties={'a':'b'}, repository='rep', project='prj',
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
                        'who': 'me'}))
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


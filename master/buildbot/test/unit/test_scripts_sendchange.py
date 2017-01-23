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

from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

from buildbot.clients import sendchange as sendchange_client
from buildbot.scripts import sendchange
from buildbot.test.util import misc


class TestSendChange(misc.StdoutAssertionsMixin, unittest.TestCase):

    class FakeSender:

        def __init__(self, testcase, master, auth, encoding=None):
            self.master = master
            self.auth = auth
            self.encoding = encoding
            self.testcase = testcase

        def send(self, branch, revision, comments, files, **kwargs):
            kwargs['branch'] = branch
            kwargs['revision'] = revision
            kwargs['comments'] = comments
            kwargs['files'] = files
            self.send_kwargs = kwargs
            d = defer.Deferred()
            if self.testcase.fail:
                reactor.callLater(0, d.errback, RuntimeError("oh noes"))
            else:
                reactor.callLater(0, d.callback, None)
            return d

    def setUp(self):
        self.fail = False  # set to true to get Sender.send to fail

        def Sender_constr(*args, **kwargs):
            self.sender = self.FakeSender(self, *args, **kwargs)
            return self.sender
        self.patch(sendchange_client, 'Sender', Sender_constr)

        # undo the effects of @in_reactor
        self.patch(sendchange, 'sendchange', sendchange.sendchange._orig)

        self.setUpStdoutAssertions()

    def test_sendchange_config(self):
        d = sendchange.sendchange(dict(encoding='utf16', who='me',
                                       auth=['a', 'b'], master='m', branch='br', category='cat',
                                       revision='rr', properties={'a': 'b'}, repository='rep',
                                       project='prj', vc='git', revlink='rl', when=1234.0,
                                       comments='comm', files=('a', 'b'), codebase='cb'))

        def check(rc):
            self.assertEqual((self.sender.master, self.sender.auth,
                              self.sender.encoding, self.sender.send_kwargs,
                              self.getStdout(), rc),
                             ('m', ['a', 'b'], 'utf16', {
                                 'branch': 'br',
                                 'category': 'cat',
                                 'codebase': 'cb',
                                 'comments': 'comm',
                                 'files': ('a', 'b'),
                                 'project': 'prj',
                                 'properties': {'a': 'b'},
                                 'repository': 'rep',
                                 'revision': 'rr',
                                 'revlink': 'rl',
                                 'when': 1234.0,
                                 'who': 'me',
                                 'vc': 'git'},
                                 'change sent successfully', 0))
        d.addCallback(check)
        return d

    def test_sendchange_config_no_codebase(self):
        d = sendchange.sendchange(dict(encoding='utf16', who='me',
                                       auth=['a', 'b'], master='m', branch='br', category='cat',
                                       revision='rr', properties={'a': 'b'}, repository='rep',
                                       project='prj', vc='git', revlink='rl', when=1234.0,
                                       comments='comm', files=('a', 'b')))

        def check(rc):
            self.assertEqual((self.sender.master, self.sender.auth,
                              self.sender.encoding, self.sender.send_kwargs,
                              self.getStdout(), rc),
                             ('m', ['a', 'b'], 'utf16', {
                                 'branch': 'br',
                                 'category': 'cat',
                                 'codebase': None,
                                 'comments': 'comm',
                                 'files': ('a', 'b'),
                                 'project': 'prj',
                                 'properties': {'a': 'b'},
                                 'repository': 'rep',
                                 'revision': 'rr',
                                 'revlink': 'rl',
                                 'when': 1234.0,
                                 'who': 'me',
                                 'vc': 'git'},
                                 'change sent successfully', 0))
        d.addCallback(check)
        return d

    def test_sendchange_fail(self):
        self.fail = True
        d = sendchange.sendchange({})

        def check(rc):
            self.assertEqual((self.getStdout().split('\n')[0], rc),
                             ('change not sent:', 1))
        d.addCallback(check)
        return d

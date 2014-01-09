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

from buildbot.util import lineboundaries
from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest


class LBF(unittest.TestCase):

    def setUp(self):
        self.callbacks = []
        self.lbf = lineboundaries.LineBoundaryFinder(self._callback)

    def _callback(self, wholeLines):
        self.assertEqual(wholeLines[-1], '\n', 'got %r' % (wholeLines))
        self.callbacks.append(wholeLines)
        d = defer.Deferred()
        reactor.callLater(0, d.callback, None)
        return d

    def assertCallbacks(self, callbacks):
        self.assertEqual(self.callbacks, callbacks)
        self.callbacks = []

    # tests

    @defer.inlineCallbacks
    def test_already_terminated(self):
        yield self.lbf.append('abcd\ndefg\n')
        self.assertCallbacks(['abcd\ndefg\n'])
        yield self.lbf.append('xyz\n')
        self.assertCallbacks(['xyz\n'])
        yield self.lbf.flush()
        self.assertCallbacks([])

    @defer.inlineCallbacks
    def test_partial_line(self):
        for c in "hello\nworld":
            yield self.lbf.append(c)
        self.assertCallbacks(['hello\n'])
        yield self.lbf.flush()
        self.assertCallbacks(['world\n'])

    @defer.inlineCallbacks
    def test_empty_appends(self):
        yield self.lbf.append('hello ')
        yield self.lbf.append('')
        yield self.lbf.append('world\n')
        yield self.lbf.append('')
        self.assertCallbacks(['hello world\n'])

    @defer.inlineCallbacks
    def test_embedded_newlines(self):
        yield self.lbf.append('hello, ')
        self.assertCallbacks([])
        yield self.lbf.append('cruel\nworld')
        self.assertCallbacks(['hello, cruel\n'])
        yield self.lbf.flush()
        self.assertCallbacks(['world\n'])

    def test_empty_flush(self):
        d = self.lbf.flush()

        @d.addCallback
        def check(_):
            self.assertEqual(self.callbacks, [])
        return d

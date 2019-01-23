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


from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.trial import unittest

from buildbot.util import lineboundaries


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

    @defer.inlineCallbacks
    def test_windows_newlines_folded(self):
        r"Windows' \r\n is treated as and converted to a newline"
        yield self.lbf.append('hello, ')
        self.assertCallbacks([])
        yield self.lbf.append('cruel\r\n\r\nworld')
        self.assertCallbacks(['hello, cruel\n\n'])
        yield self.lbf.flush()
        self.assertCallbacks(['world\n'])

    @defer.inlineCallbacks
    def test_bare_cr_folded(self):
        r"a bare \r is treated as and converted to a newline"
        yield self.lbf.append('1%\r5%\r15%\r100%\nfinished')
        yield self.lbf.flush()
        self.assertCallbacks(['1%\n5%\n15%\n100%\n', 'finished\n'])

    @defer.inlineCallbacks
    def test_backspace_folded(self):
        r"a lot of \b is treated as and converted to a newline"
        yield self.lbf.append('1%\b\b5%\b\b15%\b\b\b100%\nfinished')
        yield self.lbf.flush()
        self.assertCallbacks(['1%\n5%\n15%\n100%\n', 'finished\n'])

    @defer.inlineCallbacks
    def test_mixed_consecutive_newlines(self):
        r"mixing newline styles back-to-back doesn't collapse them"
        yield self.lbf.append('1\r\n\n\r')
        self.assertCallbacks(['1\n\n'])  # last \r is delayed until flush
        yield self.lbf.append('2\n\r\n')
        self.assertCallbacks(['\n2\n\n'])

    @defer.inlineCallbacks
    def test_split_newlines(self):
        r"multi-character newlines, split across chunks, are converted"
        input = 'a\nb\r\nc\rd\n\re'
        for splitpoint in range(1, len(input) - 1):
            a, b = input[:splitpoint], input[splitpoint:]
            yield self.lbf.append(a)
            yield self.lbf.append(b)
            yield self.lbf.flush()
            res = ''.join(self.callbacks)
            log.msg('feeding %r, %r gives %r' % (a, b, res))
            self.assertEqual(res, 'a\nb\nc\nd\n\ne\n')
            self.callbacks = []

    @defer.inlineCallbacks
    def test_split_terminal_control(self):
        """terminal control characters are converted"""
        yield self.lbf.append('1234\033[u4321')
        yield self.lbf.flush()
        self.assertCallbacks(['1234\n', '4321\n'])
        yield self.lbf.append('1234\033[1;2H4321')
        yield self.lbf.flush()
        self.assertCallbacks(['1234\n', '4321\n'])
        yield self.lbf.append('1234\033[1;2f4321')
        yield self.lbf.flush()
        self.assertCallbacks(['1234\n', '4321\n'])

    @defer.inlineCallbacks
    def test_long_lines(self):
        """long lines are split"""
        for i in range(4):
            yield self.lbf.append('12' * 1000)
        # a split at 4096 + the remaining chars
        self.assertCallbacks(['12' * 2048 + '\n' + '12' * 952 + '\n'])

    @defer.inlineCallbacks
    def test_huge_lines(self):
        """huge lines are split"""
        yield self.lbf.append('12' * 32768)
        yield self.lbf.flush()
        self.assertCallbacks([('12' * 2048 + '\n') * 16])

    @defer.inlineCallbacks
    def test_empty_flush(self):
        yield self.lbf.flush()

        self.assertEqual(self.callbacks, [])

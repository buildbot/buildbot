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


from twisted.python import log
from twisted.trial import unittest

from buildbot_worker.util import lineboundaries


class LBF(unittest.TestCase):

    def setUp(self):
        self.lbf = lineboundaries.LineBoundaryFinder()

    # tests

    def test_already_terminated(self):
        res = self.lbf.append('abcd\ndefg\n')
        self.assertEqual(res, 'abcd\ndefg\n')
        res = self.lbf.append('xyz\n')
        self.assertEqual(res, 'xyz\n')
        res = self.lbf.flush()
        self.assertEqual(res, None)

    def test_partial_line(self):
        res = self.lbf.append('hello\nworld')
        self.assertEqual(res, 'hello\n')
        res = self.lbf.flush()
        self.assertEqual(res, 'world\n')

    def test_empty_appends(self):
        res = self.lbf.append('hello ')
        self.assertEqual(res, None)

        res = self.lbf.append('')
        self.assertEqual(res, None)

        res = self.lbf.append('world\n')
        self.assertEqual(res, 'hello world\n')

        res = self.lbf.append('')
        self.assertEqual(res, None)

    def test_embedded_newlines(self):
        res = self.lbf.append('hello, ')
        self.assertEqual(res, None)

        res = self.lbf.append('cruel\nworld')
        self.assertEqual(res, 'hello, cruel\n')

        res = self.lbf.flush()
        self.assertEqual(res, 'world\n')

    def test_windows_newlines_folded(self):
        r"Windows' \r\n is treated as and converted to a newline"
        res = self.lbf.append('hello, ')
        self.assertEqual(res, None)

        res = self.lbf.append('cruel\r\n\r\nworld')
        self.assertEqual(res, 'hello, cruel\n\n')

        res = self.lbf.flush()
        self.assertEqual(res, 'world\n')

    def test_bare_cr_folded(self):
        r"a bare \r is treated as and converted to a newline"
        self.lbf.append('1%\r5%\r15%\r100%\nfinished')
        res = self.lbf.flush()
        self.assertEqual(res, 'finished\n')

    def test_backspace_folded(self):
        r"a lot of \b is treated as and converted to a newline"
        self.lbf.append('1%\b\b5%\b\b15%\b\b\b100%\nfinished')
        res = self.lbf.flush()
        self.assertEqual(res, 'finished\n')

    def test_mixed_consecutive_newlines(self):
        r"mixing newline styles back-to-back doesn't collapse them"
        res = self.lbf.append('1\r\n\n\r')
        self.assertEqual(res, '1\n\n')

        res = self.lbf.append('2\n\r\n')
        self.assertEqual(res, '\n2\n\n')

    def test_split_newlines(self):
        r"multi-character newlines, split across chunks, are converted"
        input = 'a\nb\r\nc\rd\n\re'
        result = []
        for splitpoint in range(1, len(input) - 1):
            a, b = input[:splitpoint], input[splitpoint:]
            result.append(self.lbf.append(a))
            result.append(self.lbf.append(b))
            result.append(self.lbf.flush())

            result = [e for e in result if e is not None]
            res = ''.join(result)

            log.msg('feeding {}, {} gives {}'.format(repr(a), repr(b), repr(res)))
            self.assertEqual(res, 'a\nb\nc\nd\n\ne\n')
            del result[:]

    def test_split_terminal_control(self):
        """terminal control characters are converted"""
        res = self.lbf.append('1234\033[u4321')
        self.assertEqual(res, '1234\n')

        res = self.lbf.flush()
        self.assertEqual(res, '4321\n')

        res = self.lbf.append('1234\033[1;2H4321')
        self.assertEqual(res, '1234\n')

        res = self.lbf.flush()
        self.assertEqual(res, '4321\n')

        res = self.lbf.append('1234\033[1;2f4321')
        self.assertEqual(res, '1234\n')

        res = self.lbf.flush()
        self.assertEqual(res, '4321\n')

    def test_long_lines(self):
        """long lines are split"""
        res = []
        for _ in range(4):
            res.append(self.lbf.append('12' * 1000))
        res = [e for e in res if e is not None]
        res = ''.join(res)
        # a split at 4096 + the remaining chars
        self.assertEqual(res, '12' * 2048 + '\n' + '12' * 952 + '\n')

    def test_huge_lines(self):
        """huge lines are split"""
        res = []
        res.append(self.lbf.append('12' * 32768))
        res.append(self.lbf.flush())
        res = [e for e in res if e is not None]
        self.assertEqual(res, [('12' * 2048 + '\n') * 16])

    def test_empty_flush(self):
        res = self.lbf.flush()
        self.assertEqual(res, None)

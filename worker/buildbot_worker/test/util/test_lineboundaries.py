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

from buildbot_worker.util import lineboundaries


def join_line_info(info1, info2):
    len_text1 = len(info1[0])
    return (
        info1[0] + info2[0],
        info1[1] + [(len_text1 + index) for index in info2[1]],
        info1[2] + info2[2]
    )


class LBF(unittest.TestCase):

    def setUp(self):
        newline_re = r'(\r\n|\r(?=.)|\033\[u|\033\[[0-9]+;[0-9]+[Hf]|\033\[2J|\x08+)'
        self.lbf = lineboundaries.LineBoundaryFinder(20, newline_re)

    def test_empty_line(self):
        self.assertEqual(self.lbf.append('1234', 1.0), None)
        self.assertEqual(self.lbf.append('\n', 2.0), ('1234\n', [4], [1.0]))
        self.assertEqual(self.lbf.append('5678\n', 3.0), ('5678\n', [4], [3.0]))
        self.assertEqual(self.lbf.flush(), None)

    def test_already_terminated(self):
        self.assertEqual(self.lbf.append('abcd\ndefg\n', 1.0), ('abcd\ndefg\n', [4, 9], [1.0, 1.0]))
        self.assertEqual(self.lbf.append('xyz\n', 2.0), ('xyz\n', [3], [2.0]))
        self.assertEqual(self.lbf.flush(), None)

    def test_partial_line(self):
        self.assertEqual(self.lbf.append('hello\nworld', 1.0), ('hello\n', [5], [1.0]))
        self.assertEqual(self.lbf.flush(), ('world\n', [5], [1.0]))

    def test_empty_appends(self):
        self.assertEqual(self.lbf.append('hello ', 1.0), None)
        self.assertEqual(self.lbf.append('', 2.0), None)
        self.assertEqual(self.lbf.append('world\n', 3.0), ('hello world\n', [11], [1.0]))
        self.assertEqual(self.lbf.append('', 1.0), None)

    def test_embedded_newlines(self):
        self.assertEqual(self.lbf.append('hello, ', 1.0), None)
        self.assertEqual(self.lbf.append('cruel\nworld', 2.0), ('hello, cruel\n', [12], [1.0]))
        self.assertEqual(self.lbf.flush(), ('world\n', [5], [2.0]))

    def test_windows_newlines_folded(self):
        r"Windows' \r\n is treated as and converted to a newline"
        self.assertEqual(self.lbf.append('hello, ', 1.0), None)
        self.assertEqual(self.lbf.append('cruel\r\n\r\nworld', 2.0),
                         ('hello, cruel\n\n', [12, 13], [1.0, 2.0]))
        self.assertEqual(self.lbf.flush(), ('world\n', [5], [2.0]))

    def test_bare_cr_folded(self):
        r"a bare \r is treated as and converted to a newline"
        self.assertEqual(self.lbf.append('1%\r5%\r15%\r100%\nfinished', 1.0),
                         ('1%\n5%\n15%\n100%\n', [2, 5, 9, 14], [1.0, 1.0, 1.0, 1.0]))
        self.assertEqual(self.lbf.flush(), ('finished\n', [8], [1.0]))

    def test_backspace_folded(self):
        r"a lot of \b is treated as and converted to a newline"
        self.lbf.append('1%\b\b5%\b\b15%\b\b\b100%\nfinished', 1.0)
        self.assertEqual(self.lbf.flush(), ('finished\n', [8], [1.0]))

    def test_mixed_consecutive_newlines(self):
        r"mixing newline styles back-to-back doesn't collapse them"
        self.assertEqual(self.lbf.append('1\r\n\n\r', 1.0), ('1\n\n', [1, 2], [1.0, 1.0]))
        self.assertEqual(self.lbf.append('2\n\r\n', 2.0), ('\n2\n\n', [0, 2, 3], [1.0, 2.0, 2.0]))

    def test_split_newlines(self):
        r"multi-character newlines, split across chunks, are converted"
        input = 'a\nb\r\nc\rd\n\re'

        for splitpoint in range(1, len(input) - 1):
            a, b = input[:splitpoint], input[splitpoint:]
            lines_info = []
            lines_info.append(self.lbf.append(a, 2.0))
            lines_info.append(self.lbf.append(b, 2.0))
            lines_info.append(self.lbf.flush())

            lines_info = [e for e in lines_info if e is not None]

            joined_line_info = lines_info[0]
            for line_info in lines_info[1:]:
                joined_line_info = join_line_info(joined_line_info, line_info)
            self.assertEqual(joined_line_info,
                             ('a\nb\nc\nd\n\ne\n', [1, 3, 5, 7, 8, 10],
                              [2.0, 2.0, 2.0, 2.0, 2.0, 2.0]))

    def test_split_terminal_control(self):
        """terminal control characters are converted"""
        self.assertEqual(self.lbf.append('1234\033[u4321', 1.0), ('1234\n', [4], [1.0]))
        self.assertEqual(self.lbf.flush(), ('4321\n', [4], [1.0]))
        self.assertEqual(self.lbf.append('1234\033[1;2H4321', 2.0), ('1234\n', [4], [2.0]))
        self.assertEqual(self.lbf.flush(), ('4321\n', [4], [2.0]))
        self.assertEqual(self.lbf.append('1234\033[1;2f4321', 3.0), ('1234\n', [4], [3.0]))
        self.assertEqual(self.lbf.flush(), ('4321\n', [4], [3.0]))

    def test_long_lines(self):
        """long lines are split"""
        self.assertEqual(self.lbf.append('123456789012', 1.0), None)
        self.assertEqual(self.lbf.append('123456789012', 2.0),
                         ('1234567890121234567\n', [19], [1.0]))
        self.assertEqual(self.lbf.append('123456789012345', 3.0),
                         ('8901212345678901234\n', [19], [2.0]))
        self.assertEqual(self.lbf.append('123456789012', 4.0), None)
        self.assertEqual(self.lbf.flush(), ('5123456789012\n', [13], [3.0]))

    def test_empty_flush(self):
        self.assertEqual(self.lbf.flush(), None)

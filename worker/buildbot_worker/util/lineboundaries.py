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


import re

from twisted.logger import Logger

log = Logger()


class LineBoundaryFinder:

    __slots__ = ['max_line_length', 'newline_re', 'partial_line', 'warned', 'time']

    def __init__(self, max_line_length, newline_re):
        # split at reasonable line length.
        # too big lines will fill master's memory, and slow down the UI too much.
        self.max_line_length = max_line_length
        self.newline_re = re.compile(newline_re)
        self.partial_line = ""
        self.warned = False
        self.time = None

    def append(self, text, time):
        # returns a tuple containing three elements:
        # - text: string containing one or more lines
        # - lf_positions: newline position in returned string
        # - line times: times when first line symbol was received
        had_partial_line = False
        if self.partial_line:
            had_partial_line = True
            text = self.partial_line + text
            time_partial_line = self.time

        text = self.newline_re.sub('\n', text)

        lf_positions = self.get_lf_positions(text)

        ret_lines = []  # lines with appropriate number of symbols and their separators \n
        ret_indexes = []  # ret_indexes is a list of '\n' symbols
        ret_text_length = -1
        ret_line_count = 0

        first_position = 0
        for position in lf_positions:
            # finds too long lines and splits them, each element in ret_lines will be a line of
            # appropriate length
            while position - first_position >= self.max_line_length:
                line = text[first_position: self.max_line_length - 1] + '\n'
                ret_lines.append(line)
                ret_line_count += 1
                ret_text_length = ret_text_length + len(line)
                ret_indexes.append(ret_text_length)
                first_position = first_position + self.max_line_length

            line = text[first_position: (position + 1)]
            ret_lines.append(line)
            ret_line_count += 1
            ret_text_length = ret_text_length + len(line)
            ret_indexes.append(ret_text_length)
            first_position = position + 1

        position = len(text)
        while position - first_position >= self.max_line_length:
            line = text[first_position: self.max_line_length - 1] + '\n'
            ret_lines.append(line)
            ret_text_length = ret_text_length + len(line)
            ret_indexes.append(ret_text_length)
            first_position = first_position + self.max_line_length - 1

        if had_partial_line:
            times = []
            if ret_line_count > 1:
                times = [time] * (ret_line_count - 1)
            line_times = [time_partial_line] + times
        else:
            line_times = ret_line_count * [time]

        ret_text = "".join(ret_lines)

        if ret_text != '' or not had_partial_line:
            self.time = time

        self.partial_line = text[first_position: position]

        if ret_text == '':
            return None

        return (ret_text, ret_indexes, line_times)

    def get_lf_positions(self, text):
        lf_position = 0
        lf_positions = []
        while lf_position != -1:
            lf_position = text.find('\n', lf_position)
            if lf_position < 0:
                break
            lf_positions.append(lf_position)
            lf_position = lf_position + 1
        return lf_positions

    def flush(self):
        if self.partial_line != "":
            return self.append('\n', self.time)
        return None

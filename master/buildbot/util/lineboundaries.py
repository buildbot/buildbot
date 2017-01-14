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

import re

from twisted.internet import defer


class LineBoundaryFinder(object):

    __slots__ = ['partialLine', 'callback']

    # the lookahead here (`(?=.)`) ensures that `\r` doesn't match at the end
    # of the buffer
    newline_re = re.compile(r'(\r\n|\r(?=.)|\n)')

    def __init__(self, callback):
        self.partialLine = None
        self.callback = callback

    def append(self, text):
        if self.partialLine:
            text = self.partialLine + text
            self.partialLine = None
        text = self.newline_re.sub('\n', text)
        if text:
            if text[-1] != '\n':
                i = text.rfind('\n')
                if i >= 0:
                    i = i + 1
                    text, self.partialLine = text[:i], text[i:]
                else:
                    self.partialLine = text
                    return defer.succeed(None)
            return self.callback(text)
        return defer.succeed(None)

    def flush(self):
        if self.partialLine:
            return self.append('\n')
        return defer.succeed(None)

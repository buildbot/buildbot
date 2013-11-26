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


class LineBoundaryFinder(object):

    __slots__ = ['partialLine', 'callback']

    def __init__(self, callback):
        self.partialLine = None
        self.callback = callback

    def append(self, text):
        if self.partialLine:
            text = self.partialLine + text
            self.partialLine = None
        if text[-1] != '\n':
            i = text.rfind('\n')
            if i >= 0:
                i = i + 1
                text, self.partialLine = text[:i], text[i:]
            else:
                self.partialLine = text
                return defer.succeed(None)
        return self.callback(text)

    def flush(self):
        if self.partialLine:
            return self.append('\n')
        else:
            return defer.succeed(None)

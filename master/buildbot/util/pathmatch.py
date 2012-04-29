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

class Matcher(object):

    def __init__(self):
        self._patterns = {}
        self._dirty = True

    def __setitem__(self, path, value):
        assert path not in self._patterns, "duplicate path"
        self._patterns[path] = value
        self._dirty = True

    def __getitem__(self, path):
        if self._dirty:
            self._compile()

        patterns = self._by_length.get(len(path), {})
        for pattern in patterns:
            kwargs = {}
            for ptrn, pth in zip(pattern, path):
                if ptrn[0] == ':':
                    kwargs[ptrn[1:]] = pth
                else:
                    if ptrn != pth:
                        break
            else:
                # complete match
                return patterns[pattern], kwargs
        else:
            raise KeyError, 'No match for %r' % (path,)

    def _compile(self):
        self._by_length = {}
        for k, v in self._patterns.iteritems():
            l = len(k)
            self._by_length.setdefault(l, {})[k] = v

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
from future.utils import iteritems

import re

_ident_re = re.compile('^[a-zA-Z_-][.a-zA-Z0-9_-]*$')


def ident(x):
    if _ident_re.match(x):
        return x
    raise TypeError


class Matcher(object):

    def __init__(self):
        self._patterns = {}
        self._dirty = True

    def __setitem__(self, path, value):
        assert path not in self._patterns, "duplicate path %s" % (path,)
        self._patterns[path] = value
        self._dirty = True

    def __repr__(self):
        return '<Matcher %r>' % (self._patterns,)

    path_elt_re = re.compile('^(.?):([a-z0-9_.]+)$')
    type_fns = dict(n=int, i=ident)

    def __getitem__(self, path):
        if self._dirty:
            self._compile()

        patterns = self._by_length.get(len(path), {})
        for pattern in patterns:
            kwargs = {}
            for pattern_elt, path_elt in zip(pattern, path):
                mo = self.path_elt_re.match(pattern_elt)
                if mo:
                    type_flag, arg_name = mo.groups()
                    if type_flag:
                        try:
                            type_fn = self.type_fns[type_flag]
                        except Exception:
                            assert type_flag in self.type_fns, \
                                "no such type flag %s" % type_flag
                        try:
                            path_elt = type_fn(path_elt)
                        except Exception:
                            break
                    kwargs[arg_name] = path_elt
                else:
                    if pattern_elt != path_elt:
                        break
            else:
                # complete match
                return patterns[pattern], kwargs
        else:
            raise KeyError('No match for %r' % (path,))

    def iterPatterns(self):
        return list(iteritems(self._patterns))

    def _compile(self):
        self._by_length = {}
        for k, v in self.iterPatterns():
            length = len(k)
            self._by_length.setdefault(length, {})[k] = v

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

from future.utils import iteritems
from twisted.python.components import registerAdapter
from zope.interface import implements

from buildbot.interfaces import IConfigured


class _DefaultConfigured(object):
    implements(IConfigured)

    def __init__(self, value):
        self.value = value

    def getConfigDict(self):
        return self.value

registerAdapter(_DefaultConfigured, object, IConfigured)


class _ListConfigured(object):
    implements(IConfigured)

    def __init__(self, value):
        self.value = value

    def getConfigDict(self):
        return [IConfigured(e).getConfigDict() for e in self.value]

registerAdapter(_ListConfigured, list, IConfigured)


class _DictConfigured(object):
    implements(IConfigured)

    def __init__(self, value):
        self.value = value

    def getConfigDict(self):
        return dict([(k, IConfigured(v).getConfigDict()) for k, v in iteritems(self.value)])

registerAdapter(_DictConfigured, dict, IConfigured)


class _SREPatternConfigured(object):
    implements(IConfigured)

    def __init__(self, value):
        self.value = value

    def getConfigDict(self):
        return dict(name="re", pattern=self.value.pattern)

registerAdapter(_SREPatternConfigured, type(re.compile("")), IConfigured)


class ConfiguredMixin(object):
    implements(IConfigured)

    def getConfigDict(self):
        return {'name': self.name}

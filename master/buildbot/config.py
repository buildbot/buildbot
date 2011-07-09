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

from buildbot.util import safeTranslate


class MasterConfig(object):
    """
    Namespace for master configuration values.  An instance of this class is
    available at C{master.config}.

    @ivar changeHorizon: the current change horizon
    @ivar validation: regexes for preventing invalid inputs
    """

    changeHorizon = None

class BuilderConfig:
    """

    Used in config files to specify a builder - this can be subclassed by users
    to add extra config args, set defaults, or whatever.  It is converted to a
    dictionary for consumption by the buildmaster at config time.

    """

    def __init__(self,
                name=None,
                slavename=None,
                slavenames=None,
                builddir=None,
                slavebuilddir=None,
                factory=None,
                category=None,
                nextSlave=None,
                nextBuild=None,
                locks=None,
                env=None,
                properties=None,
                mergeRequests=None):

        # name is required, and can't start with '_'
        if not name or type(name) not in (str, unicode):
            raise ValueError("builder's name is required")
        if name[0] == '_':
            raise ValueError("builder names must not start with an "
                             "underscore: " + name)
        self.name = name

        # factory is required
        if factory is None:
            raise ValueError("builder's factory is required")
        self.factory = factory

        # slavenames can be a single slave name or a list, and should also
        # include slavename, if given
        if type(slavenames) is str:
            slavenames = [ slavenames ]
        if slavenames:
            if type(slavenames) is not list:
                raise TypeError("slavenames must be a list or a string")
        else:
            slavenames = []
        if slavename:
            if type(slavename) != str:
                raise TypeError("slavename must be a string")
            slavenames = slavenames + [ slavename ]
        if not slavenames:
            raise ValueError("at least one slavename is required")
        self.slavenames = slavenames

        # builddir defaults to name
        if builddir is None:
            builddir = safeTranslate(name)
        self.builddir = builddir

        # slavebuilddir defaults to builddir
        if slavebuilddir is None:
            slavebuilddir = builddir
        self.slavebuilddir = slavebuilddir

        # remainder are optional
        assert category is None or isinstance(category, str)
        self.category = category
        self.nextSlave = nextSlave
        self.nextBuild = nextBuild
        self.locks = locks
        self.env = env
        self.properties = properties
        self.mergeRequests = mergeRequests

    def getConfigDict(self):
        rv = {
            'name': self.name,
            'slavenames': self.slavenames,
            'factory': self.factory,
            'builddir': self.builddir,
            'slavebuilddir': self.slavebuilddir,
        }
        if self.category:
            rv['category'] = self.category
        if self.nextSlave:
            rv['nextSlave'] = self.nextSlave
        if self.nextBuild:
            rv['nextBuild'] = self.nextBuild
        if self.locks:
            rv['locks'] = self.locks
        if self.env:
            rv['env'] = self.env
        if self.properties:
            rv['properties'] = self.properties
        if self.mergeRequests:
            rv['mergeRequests'] = self.mergeRequests
        return rv

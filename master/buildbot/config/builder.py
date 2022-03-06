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


from buildbot.config.checks import check_param_length
from buildbot.config.errors import error
from buildbot.db.model import Model
from buildbot.util import bytes2unicode
from buildbot.util import config as util_config
from buildbot.util import safeTranslate

RESERVED_UNDERSCORE_NAMES = ["__Janitor"]


class BuilderConfig(util_config.ConfiguredMixin):

    def __init__(self, name=None, workername=None, workernames=None,
                 builddir=None, workerbuilddir=None, factory=None,
                 tags=None,
                 nextWorker=None, nextBuild=None, locks=None, env=None,
                 properties=None, collapseRequests=None, description=None,
                 canStartBuild=None, defaultProperties=None
                 ):
        # name is required, and can't start with '_'
        if not name or type(name) not in (bytes, str):
            error("builder's name is required")
            name = '<unknown>'
        elif name[0] == '_' and name not in RESERVED_UNDERSCORE_NAMES:
            error(f"builder names must not start with an underscore: '{name}'")
        try:
            self.name = bytes2unicode(name, encoding="ascii")
        except UnicodeDecodeError:
            error("builder names must be unicode or ASCII")

        # factory is required
        if factory is None:
            error(f"builder '{name}' has no factory")
        from buildbot.process.factory import BuildFactory
        if factory is not None and not isinstance(factory, BuildFactory):
            error(f"builder '{name}'s factory is not a BuildFactory instance")
        self.factory = factory

        # workernames can be a single worker name or a list, and should also
        # include workername, if given
        if isinstance(workernames, str):
            workernames = [workernames]
        if workernames:
            if not isinstance(workernames, list):
                error(f"builder '{name}': workernames must be a list or a string")
        else:
            workernames = []

        if workername:
            if not isinstance(workername, str):
                error(f"builder '{name}': workername must be a string but it is {repr(workername)}")
            workernames = workernames + [workername]
        if not workernames:
            error(f"builder '{name}': at least one workername is required")

        self.workernames = workernames

        # builddir defaults to name
        if builddir is None:
            builddir = safeTranslate(name)
            builddir = bytes2unicode(builddir)
        self.builddir = builddir

        # workerbuilddir defaults to builddir
        if workerbuilddir is None:
            workerbuilddir = builddir
        self.workerbuilddir = workerbuilddir

        # remainder are optional
        if tags:
            if not isinstance(tags, list):
                error(f"builder '{name}': tags must be a list")
            bad_tags = any((tag for tag in tags if not isinstance(tag, str)))
            if bad_tags:
                error(f"builder '{name}': tags list contains something that is not a string")

            if len(tags) != len(set(tags)):
                dupes = " ".join({x for x in tags if tags.count(x) > 1})
                error(f"builder '{name}': tags list contains duplicate tags: {dupes}")
        else:
            tags = []

        self.tags = tags

        self.nextWorker = nextWorker
        if nextWorker and not callable(nextWorker):
            error('nextWorker must be a callable')
        self.nextBuild = nextBuild
        if nextBuild and not callable(nextBuild):
            error('nextBuild must be a callable')
        self.canStartBuild = canStartBuild
        if canStartBuild and not callable(canStartBuild):
            error('canStartBuild must be a callable')

        self.locks = locks or []
        self.env = env or {}
        if not isinstance(self.env, dict):
            error("builder's env must be a dictionary")

        self.properties = properties or {}
        for property_name in self.properties:
            check_param_length(property_name, f'Builder {self.name} property',
                               Model.property_name_length)

        self.defaultProperties = defaultProperties or {}
        for property_name in self.defaultProperties:
            check_param_length(property_name, f'Builder {self.name} default property',
                               Model.property_name_length)

        self.collapseRequests = collapseRequests

        self.description = description

    def getConfigDict(self):
        # note: this method will disappear eventually - put your smarts in the
        # constructor!
        rv = {
            'name': self.name,
            'workernames': self.workernames,
            'factory': self.factory,
            'builddir': self.builddir,
            'workerbuilddir': self.workerbuilddir,
        }
        if self.tags:
            rv['tags'] = self.tags
        if self.nextWorker:
            rv['nextWorker'] = self.nextWorker
        if self.nextBuild:
            rv['nextBuild'] = self.nextBuild
        if self.locks:
            rv['locks'] = self.locks
        if self.env:
            rv['env'] = self.env
        if self.properties:
            rv['properties'] = self.properties
        if self.defaultProperties:
            rv['defaultProperties'] = self.defaultProperties
        if self.collapseRequests is not None:
            rv['collapseRequests'] = self.collapseRequests
        if self.description:
            rv['description'] = self.description
        return rv

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

from twisted.internet import defer

from buildbot import config
from buildbot.interfaces import IRenderable
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import ShellMixin


class CMake(ShellMixin, BuildStep):
    DEFAULT_CMAKE = 'cmake'

    name = 'cmake'
    description = ['running', 'cmake']
    descriptionDone = ['cmake']

    renderables = (
        'cmake',
        'definitions',
        'generator',
        'options',
        'path'
    )

    haltOnFailure = True

    def __init__(self, path=None, generator=None, definitions=None,
                 options=None, cmake=DEFAULT_CMAKE, **kwargs):

        self.path = path
        self.generator = generator

        if not (definitions is None or isinstance(definitions, dict)
                or IRenderable.providedBy(definitions)):
            config.error('definitions must be a dictionary or implement IRenderable')
        self.definitions = definitions

        if not (options is None or isinstance(options, (list, tuple))
                or IRenderable.providedBy(options)):
            config.error('options must be a list, a tuple or implement IRenderable')
        self.options = options

        self.cmake = cmake
        kwargs = self.setupShellMixin(kwargs, prohibitArgs=['command'])
        super(CMake, self).__init__(**kwargs)

    @defer.inlineCallbacks
    def run(self):
        """
        run CMake
        """
        command = [self.cmake]

        if self.generator:
            command.extend([
                '-G', self.generator
            ])

        if self.path:
            command.append(self.path)

        if self.definitions is not None:
            for item in iteritems(self.definitions):
                command.append('-D%s=%s' % item)

        if self.options is not None:
            command.extend(self.options)

        cmd = yield self.makeRemoteShellCommand(command=command)

        yield self.runCommand(cmd)

        defer.returnValue(cmd.results())

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


from buildbot.status.results import FAILURE, SUCCESS, WARNINGS
from buildbot.steps.shell import ShellCommand
from buildbot.steps import vstudio
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps
from twisted.trial import unittest
from buildbot.process.properties import WithProperties

from mock import Mock

class testVC8(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        # a bit of monkeypatching ...
        vstudio.VisualStudio.addLogObserver = Mock()
        vstudio.VisualStudio.finished = ShellCommand.finished
        
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def testProperties(self):
        self.setupStep(vstudio.VC8(projectfile=WithProperties('%(projectfile)s'),
                                   config=WithProperties('%(config)s'),
                                   project=WithProperties('%(project)s'),
                                   arch=WithProperties('%(arch)s')))
        self.properties.setProperty('projectfile', 'project.sln', 'Test')
        self.properties.setProperty('config', 'Debug', 'Test')
        self.properties.setProperty('project', 'main', 'Test')
        self.properties.setProperty('arch', 'x64', 'Test')
        self.expectCommands(
            ExpectShell(workdir='wkdir', usePTY='slave-config',
                        command=['devenv.com',
                                 'project.sln',
                                 '/Rebuild',
                                 'Debug',
                                 '/Project',
                                 'main',
                        ],
                        env={'INCLUDE': 'C:\\Program Files\\Microsoft Visual Studio 8\\VC\\INCLUDE;C:\\Program Files\\Microsoft Visual Studio 8\\VC\\ATLMFC\\include;C:\\Program Files\\Microsoft Visual Studio 8\\VC\\PlatformSDK\\include;',
                             'LIB': 'C:\\Program Files\\Microsoft Visual Studio 8\\VC\\LIB\\amd64;C:\\Program Files\\Microsoft Visual Studio 8\\VC\\ATLMFC\\LIB\\amd64;C:\\Program Files\\Microsoft Visual Studio 8\\VC\\PlatformSDK\\lib\\amd64;C:\\Program Files\\Microsoft Visual Studio 8\\SDK\\v2.0\\lib\\amd64;',
                             'PATH': 'C:\\Program Files\\Microsoft Visual Studio 8\\Common7\\IDE;C:\\Program Files\\Microsoft Visual Studio 8\\VC\\BIN\\x86_amd64;C:\\Program Files\\Microsoft Visual Studio 8\\VC\\BIN;C:\\Program Files\\Microsoft Visual Studio 8\\Common7\\Tools;C:\\Program Files\\Microsoft Visual Studio 8\\Common7\\Tools\\bin;C:\\Program Files\\Microsoft Visual Studio 8\\VC\\PlatformSDK\\bin;C:\\Program Files\\Microsoft Visual Studio 8\\SDK\\v2.0\\bin;C:\\Program Files\\Microsoft Visual Studio 8\\VC\\VCPackages;${PATH};'},)
            + 0
        )
        self.expectOutcome(result=SUCCESS, status_text=["compile", "0 projects", "0 files"])
        return self.runStep()

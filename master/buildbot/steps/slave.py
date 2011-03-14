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

import stat
from buildbot.process.buildstep import BuildStep, LoggedRemoteCommand
from buildbot.process.buildstep import SUCCESS, FAILURE
from buildbot.interfaces import BuildSlaveTooOldError

class SetPropertiesFromEnv(BuildStep):
    """
    Sets properties from envirionment variables on the slave.

    Note this is transfered when the slave first connects
    """
    name='SetPropertiesFromEnv'
    description='Setting'
    descriptionDone='Set'

    def __init__(self, variables, source="SlaveEnvironment", **kwargs):
        BuildStep.__init__(self, **kwargs)
        self.addFactoryArguments(variables = variables,
                                 source = source)
        self.variables = variables
        self.source = source

    def start(self):
        properties = self.build.getProperties()
        environ = self.buildslave.slave_environ
        if isinstance(self.variables, str):
            self.variables = [self.variables]
        for variable in self.variables:
            value = environ.get(variable, None)
            if value:
                properties.setProperty(variable, value, self.source, runtime=True)
        self.finished(SUCCESS)

class FileExists(BuildStep):
    """
    Check for the existence of a file on the slave.
    """
    name='FileExists'
    description='Checking'
    descriptionDone='Checked'

    haltOnFailure = True
    flunkOnFailure = True


    def __init__(self, file, **kwargs):
        BuildStep.__init__(self, **kwargs)
        self.addFactoryArguments(file = file)
        self.file = file

    def start(self):
        slavever = self.slaveVersion('stat')
        if not slavever:
            raise BuildSlaveTooOldError("slave is too old, does not know "
                                        "about stat")
        cmd = LoggedRemoteCommand('stat', {'file': self.file })
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.commandComplete(cmd))
        d.addErrback(self.failed)

    def commandComplete(self, cmd):
        if cmd.rc != 0:
            self.step_status.setText(["File not found."])
            self.finished(FAILURE)
        s = cmd.updates["stat"][-1]
        if stat.S_ISREG(s[stat.ST_MODE]):
            self.step_status.setText(["File found."])
            self.finished(SUCCESS)
        else:
            self.step_status.setText(["Not a file."])
            self.finished(FAILURE)

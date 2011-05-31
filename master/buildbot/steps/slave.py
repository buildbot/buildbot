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
        # on Windows, environment variables are case-insensitive, but we have
        # a case-sensitive dictionary in slave_environ.  Fortunately, that
        # dictionary is also folded to uppercase, so we can simply fold the
        # variable names to uppercase to duplicate the case-insensitivity.
        fold_to_uppercase = (self.buildslave.slave_system == 'win32')

        properties = self.build.getProperties()
        environ = self.buildslave.slave_environ
        variables = self.variables
        if isinstance(variables, str):
            variables = [self.variables]
        for variable in variables:
            key = variable
            if fold_to_uppercase:
                key = variable.upper()
            value = environ.get(key, None)
            if value:
                # note that the property is not uppercased
                properties.setProperty(variable, value, self.source,
                                       runtime=True)
        self.finished(SUCCESS)

class FileExists(BuildStep):
    """
    Check for the existence of a file on the slave.
    """
    name='FileExists'
    description='Checking'
    descriptionDone='Checked'

    renderables = [ 'file' ]

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
            return
        s = cmd.updates["stat"][-1]
        if stat.S_ISREG(s[stat.ST_MODE]):
            self.step_status.setText(["File found."])
            self.finished(SUCCESS)
        else:
            self.step_status.setText(["Not a file."])
            self.finished(FAILURE)

class RemoveDirectory(BuildStep):
    """
    Remove a directory tree on the slave.
    """
    name='RemoveDirectory'
    description='Deleting'
    desciprtionDone='Deleted'

    renderables = [ 'dir' ]

    haltOnFailure = True
    flunkOnFailure = True

    def __init__(self, dir, **kwargs):
        BuildStep.__init__(self, **kwargs)
        self.addFactoryArguments(dir = dir)
        self.dir = dir

    def start(self):
        slavever = self.slaveVersion('rmdir')
        if not slavever:
            raise BuildSlaveTooOldError("slave is too old, does not know "
                                        "about rmdir")
        cmd = LoggedRemoteCommand('rmdir', {'dir': self.dir })
        d = self.runCommand(cmd)
        d.addCallback(lambda res: self.commandComplete(cmd))
        d.addErrback(self.failed)

    def commandComplete(self, cmd):
        if cmd.rc != 0:
            self.step_status.setText(["Delete failed."])
            self.finished(FAILURE)
            return
        self.finished(SUCCESS)

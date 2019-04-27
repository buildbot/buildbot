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


from buildbot.interfaces import IMachineAction
from buildbot.machine.latent import AbstractLatentMachine


class GenericLatentMachine(AbstractLatentMachine):

    def checkConfig(self, name, start_action, stop_action, **kwargs):
        super().checkConfig(name, **kwargs)

        for action, arg_name in [(start_action, 'start_action'),
                                 (stop_action, 'stop_action')]:
            if not IMachineAction.providedBy(action):
                msg = "{} of {} does not implement required " \
                      "interface".format(arg_name, self.name)
                raise Exception(msg)

    def reconfigService(self, name, start_action, stop_action, **kwargs):
        super().reconfigService(name, **kwargs)
        self.start_action = start_action
        self.stop_action = stop_action

    def start_machine(self):
        return self.start_action.perform(self)

    def stop_machine(self):
        return self.stop_action.perform(self)

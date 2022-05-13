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
# Portions Copyright Buildbot Team Members


from buildbot.util import service
from buildbot.worker.manager import WorkerManager


class MachineManager(service.BuildbotServiceManager):
    reconfig_priority = WorkerManager.reconfig_priority + 1
    name = "MachineManager"
    managed_services_name = "machines"
    config_attr = "machines"

    @property
    def machines(self):
        return self.namedServices

    def getMachineByName(self, name):
        if name in self.machines:
            return self.machines[name]
        return None

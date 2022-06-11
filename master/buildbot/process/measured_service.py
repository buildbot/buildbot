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


from twisted.internet import defer

from buildbot.process import metrics
from buildbot.util.service import BuildbotServiceManager


class MeasuredBuildbotServiceManager(BuildbotServiceManager):
    managed_services_name = "services"

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):
        timer = metrics.Timer(f"{self.name}.reconfigServiceWithBuildbotConfig")
        timer.start()
        yield super().reconfigServiceWithBuildbotConfig(new_config)
        metrics.MetricCountEvent.log(f"num_{self.managed_services_name}",
                                     len(list(self)), absolute=True)
        timer.stop()

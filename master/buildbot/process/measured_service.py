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

from twisted.internet import defer

from buildbot.process import metrics
from buildbot.util.service import BuildbotServiceManager


class MeasuredBuildbotServiceManager(BuildbotServiceManager):
    managed_services_name = "services"

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):
        timer = metrics.Timer(
            "{0}.reconfigServiceWithBuildbotConfig".format(self.name))
        timer.start()
        yield super(MeasuredBuildbotServiceManager, self).reconfigServiceWithBuildbotConfig(new_config)
        metrics.MetricCountEvent.log("num_{0}".format(self.managed_services_name),
                                     len(list(self)), absolute=True)
        timer.stop()

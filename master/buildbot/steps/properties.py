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
from future.utils import iteritems

from buildbot.process import buildstep
from buildbot.process.results import SUCCESS


class SetProperties(buildstep.BuildStep):
    renderables = ['properties']

    def __init__(self, properties=None, **kwargs):
        buildstep.BuildStep.__init__(self, **kwargs)
        self.properties = properties

    def run(self):
        print self.properties
        if self.properties is None:
            return SUCCESS
        for k, v in iteritems(self.properties):
            self.setProperty(k, v, self.name)
        return SUCCESS

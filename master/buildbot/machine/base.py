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

from zope.interface import implementer

from buildbot import interfaces
from buildbot.util import service


@implementer(interfaces.IMachine)
class Machine(service.BuildbotService):

    def checkConfig(self, name, **kwargs):
        super().checkConfig(**kwargs)
        self.name = name

    def reconfigService(self, name, **kwargs):
        super().reconfigService(**kwargs)
        assert self.name == name

    def __repr__(self):
        return "<Machine '{}' at {}>".format(self.name, id(self))

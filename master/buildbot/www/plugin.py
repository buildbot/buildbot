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


import importlib_resources

from twisted.web import static

from buildbot.util import bytes2unicode


class Application:

    def __init__(self, modulename, description, ui=True):
        self.description = description
        self.version = importlib_resources.files(modulename).joinpath("VERSION")
        self.version = bytes2unicode(self.version.read_bytes())
        self.static_dir = importlib_resources.files(modulename) / "static"
        self.resource = static.File(self.static_dir)
        self.ui = ui

    def setMaster(self, master):
        self.master = master

    def setConfiguration(self, config):
        self.config = config

    def __repr__(self):
        return ("www.plugin.Application(version=%(version)s, "
                "description=%(description)s, "
                "static_dir=%(static_dir)s)") % self.__dict__

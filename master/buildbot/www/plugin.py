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

import pkg_resources

from twisted.web import static

from buildbot.util import bytes2NativeString


class Application(object):

    def __init__(self, modulename, description):
        self.description = description
        self.version = pkg_resources.resource_string(
            modulename, "/VERSION").strip()
        self.version = bytes2NativeString(self.version)
        self.static_dir = pkg_resources.resource_filename(
            modulename, "/static")
        self.resource = static.File(self.static_dir)

    def setMaster(self, master):
        self.master = master

    def setConfiguration(self, config):
        self.config = config

    def __repr__(self):
        return ("www.plugin.Application(version=%(version)s, "
                "description=%(description)s, "
                "static_dir=%(static_dir)s)") % self.__dict__

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

import pkg_resources

from twisted.web import static

class Application(object):
    def __init__(self, modulename, description):
        self.description = description
        self.version = pkg_resources.resource_string(modulename, "/VERSION").strip()
        self.static_dir = pkg_resources.resource_filename(modulename, "/static")
        self.resource = static.File(self.static_dir)

    def __repr__(self):
        return "www.plugin.Application(version={}, description={}, static_dir={})".format(
            self.version, self.description, self.static_dir)

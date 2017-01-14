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


class Domain(object):

    def __init__(self, name, conn):
        self.conn = conn
        self._name = name
        self.running = False

    def name(self):
        return self._name

    def create(self):
        self.running = True

    def shutdown(self):
        self.running = False

    def destroy(self):
        self.running = False
        del self.conn[self._name]


class Connection(object):

    def __init__(self, uri):
        self.uri = uri
        self.domains = {}

    def createXML(self, xml, flags):
        # FIXME: This should really parse the name out of the xml, i guess
        d = self.fake_add("instance")
        d.running = True
        return d

    def listDomainsID(self):
        return list(self.domains)

    def lookupByName(self, name):
        return self.domains[name]

    def lookupByID(self, ID):
        return self.domains[ID]

    def fake_add(self, name):
        d = Domain(name, self)
        self.domains[name] = d
        return d


def open(uri):
    return Connection(uri)

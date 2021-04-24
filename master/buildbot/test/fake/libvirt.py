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


class Domain:

    def __init__(self, name, conn, libvirt_id):
        self.conn = conn
        self._name = name
        self.running = False
        self.libvirt_id = libvirt_id
        self.metadata = {}

    def ID(self):
        return self.libvirt_id

    def name(self):
        return self._name

    def create(self):
        self.running = True

    def shutdown(self):
        self.running = False

    def destroy(self):
        self.running = False
        del self.conn[self._name]

    def setMetadata(self, type, metadata, key, uri, flags):
        self.metadata[key] = (type, uri, metadata, flags)


class Connection:

    def __init__(self, uri):
        self.uri = uri
        self.domains = {}
        self._next_libvirt_id = 1

    def createXML(self, xml, flags):
        # FIXME: This should really parse the name out of the xml, i guess
        d = self.fake_add("instance", self._next_libvirt_id)
        self._next_libvirt_id += 1
        d.running = True
        return d

    def listDomainsID(self):
        return list(self.domains)

    def lookupByName(self, name):
        return self.domains.get(name, None)

    def lookupByID(self, ID):
        for d in self.domains.values():
            if d.ID == ID:
                return d
        return None

    def fake_add(self, name, libvirt_id):
        d = Domain(name, self, libvirt_id)
        self.domains[name] = d
        return d

    def fake_add_domain(self, name, d):
        self.domains[name] = d

    def registerCloseCallback(self, c, c2):
        pass


def open(uri):
    raise NotImplementedError('this must be patched in tests')


VIR_DOMAIN_AFFECT_CONFIG = 2
VIR_DOMAIN_METADATA_ELEMENT = 2


class libvirtError(Exception):
    pass

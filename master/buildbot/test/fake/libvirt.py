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

from __future__ import annotations

from typing import Any


class Domain:
    def __init__(self, name: str, conn: Any, libvirt_id: int) -> None:
        self.conn = conn
        self._name = name
        self.running = False
        self.libvirt_id = libvirt_id
        self.metadata: dict[str, tuple[Any, ...]] = {}

    def ID(self) -> int:
        return self.libvirt_id

    def name(self) -> str:
        return self._name

    def create(self) -> None:
        self.running = True

    def shutdown(self) -> None:
        self.running = False

    def destroy(self) -> None:
        self.running = False
        del self.conn[self._name]

    def setMetadata(self, type: Any, metadata: str, key: str, uri: str, flags: Any) -> None:
        self.metadata[key] = (type, uri, metadata, flags)


class Connection:
    def __init__(self, uri: str) -> None:
        self.uri = uri
        self.domains: dict[str, Domain] = {}
        self._next_libvirt_id = 1

    def createXML(self, xml: str, flags: Any) -> Domain:
        # FIXME: This should really parse the name out of the xml, i guess
        d = self.fake_add("instance", self._next_libvirt_id)
        self._next_libvirt_id += 1
        d.running = True
        return d

    def listDomainsID(self) -> list[str]:
        return list(self.domains)

    def lookupByName(self, name: str) -> Domain | None:
        return self.domains.get(name, None)

    def lookupByID(self, ID: int) -> Domain | None:
        for d in self.domains.values():
            if d.ID == ID:
                return d
        return None

    def fake_add(self, name: str, libvirt_id: int) -> Domain:
        d = Domain(name, self, libvirt_id)
        self.domains[name] = d
        return d

    def fake_add_domain(self, name: str, d: Domain) -> None:
        self.domains[name] = d

    def registerCloseCallback(self, c: Any, c2: Any) -> None:
        pass


def open(uri: str) -> Connection:
    raise NotImplementedError('this must be patched in tests')


VIR_DOMAIN_AFFECT_CONFIG = 2
VIR_DOMAIN_METADATA_ELEMENT = 2


class libvirtError(Exception):
    pass

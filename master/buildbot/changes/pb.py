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

from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from typing import Sequence

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.changes import base
from buildbot.pbutil import NewCredPerspective

if TYPE_CHECKING:
    from buildbot.config.master import MasterConfig
    from buildbot.util.twisted import InlineCallbacksType


class ChangePerspective(NewCredPerspective):
    def __init__(self, master: Any, prefix: str | None):
        self.master = master
        self.prefix = prefix

    def attached(self, mind: Any) -> Any:
        return self

    def detached(self, mind: Any) -> None:
        pass

    @defer.inlineCallbacks
    def perspective_addChange(self, changedict: dict[str, Any]) -> InlineCallbacksType[None]:
        log.msg("perspective_addChange called")

        if 'revlink' in changedict and not changedict['revlink']:
            changedict['revlink'] = ''
        if 'repository' in changedict and not changedict['repository']:
            changedict['repository'] = ''
        if 'project' in changedict and not changedict['project']:
            changedict['project'] = ''
        if 'files' not in changedict or not changedict['files']:
            changedict['files'] = []
        if 'committer' in changedict and not changedict['committer']:
            changedict['committer'] = None

        # rename arguments to new names.  Note that the client still uses the
        # "old" names (who, when, and isdir), as they are not deprecated yet,
        # although the master will accept the new names (author,
        # when_timestamp).  After a few revisions have passed, we
        # can switch the client to use the new names.
        if 'who' in changedict:
            changedict['author'] = changedict['who']
            del changedict['who']
        if 'when' in changedict:
            changedict['when_timestamp'] = changedict['when']
            del changedict['when']

        # turn any bytestring keys into unicode, assuming utf8 but just
        # replacing unknown characters.  Ideally client would send us unicode
        # in the first place, but older clients do not, so this fallback is
        # useful.
        for key, value in changedict.items():
            if isinstance(value, bytes):
                changedict[key] = value.decode('utf8', 'replace')
        changedict['files'] = list(changedict['files'])
        for i, file in enumerate(changedict.get('files', [])):
            if isinstance(file, bytes):
                changedict['files'][i] = file.decode('utf8', 'replace')

        files = []
        for path in changedict['files']:
            if self.prefix:
                if not path.startswith(self.prefix):
                    # this file does not start with the prefix, so ignore it
                    continue
                path = path[len(self.prefix) :]
            files.append(path)
        changedict['files'] = files

        if not files:
            log.msg("No files listed in change... bit strange, but not fatal.")

        if "links" in changedict:
            log.msg("Found links: " + repr(changedict['links']))
            del changedict['links']

        yield self.master.data.updates.addChange(**changedict)


class PBChangeSource(base.ChangeSource):
    compare_attrs: ClassVar[Sequence[str]] = ("user", "passwd", "port", "prefix", "port")

    def __init__(
        self,
        user: str = "change",
        passwd: str = "changepw",
        port: int | str | None = None,
        prefix: str | None = None,
        name: str | None = None,
    ):
        if name is None:
            if prefix:
                name = f"PBChangeSource:{prefix}:{port}"
            else:
                name = f"PBChangeSource:{port}"

        super().__init__(name=name)

        self.user = user
        self.passwd = passwd
        self.port = port
        self.prefix = prefix
        self.registration: Any = None
        self.registered_port: int | str | None = None

    def describe(self) -> str:
        portname = self.registered_port
        d = "PBChangeSource listener on " + str(portname)
        if self.prefix is not None:
            d += f" (prefix '{self.prefix}')"
        return d

    def _calculatePort(self, cfg: MasterConfig) -> int | str | None:
        # calculate the new port, defaulting to the worker's PB port if
        # none was specified
        port = self.port
        if port is None:
            port = cfg.protocols.get('pb', {}).get('port')
        return port

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(
        self, new_config: MasterConfig
    ) -> InlineCallbacksType[None]:  # type: ignore[override]
        port = self._calculatePort(new_config)
        if not port:
            config.error("No port specified for PBChangeSource, and no worker port configured")

        # and, if it's changed, re-register
        if port != self.registered_port and self.isActive():
            yield self._unregister()
            yield self._register(port)

        yield super().reconfigServiceWithBuildbotConfig(new_config)

    @defer.inlineCallbacks
    def activate(self) -> InlineCallbacksType[None]:
        port = self._calculatePort(self.master.config)
        yield self._register(port)

    def deactivate(self) -> defer.Deferred[None]:
        return self._unregister()

    @defer.inlineCallbacks
    def _register(self, port: int | str | None) -> InlineCallbacksType[None]:
        if not port:
            return
        self.registered_port = port
        self.registration = yield self.master.pbmanager.register(
            port, self.user, self.passwd, self.getPerspective
        )

    def _unregister(self) -> defer.Deferred[None]:
        self.registered_port = None
        if self.registration:
            reg = self.registration
            self.registration = None
            return reg.unregister()
        return defer.succeed(None)

    def getPerspective(self, mind: Any, username: str) -> ChangePerspective:
        assert username == self.user
        return ChangePerspective(self.master, self.prefix)

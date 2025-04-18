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

import re
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import TypeVar

from twisted.internet import defer
from twisted.python import log
from twisted.web import resource
from twisted.web import server
from twisted.web.error import Error

from buildbot.util import unicode2bytes

if TYPE_CHECKING:
    from buildbot.master import BuildMaster

_CR_LF_RE = re.compile(rb"[\r\n]+.*")
_T = TypeVar('_T')


def protect_redirect_url(url: bytes) -> bytes:
    return _CR_LF_RE.sub(b"", url)


class Redirect(Error):
    def __init__(self, url: str | bytes) -> None:
        super().__init__(302, b"redirect")
        self.url = protect_redirect_url(unicode2bytes(url))


class Resource(resource.Resource):
    # if this is true for a class, then instances will have their
    # reconfigResource(new_config) methods called on reconfig.
    needsReconfig = False

    # as a convenience, subclasses have a ``master`` attribute, a
    # ``base_url`` attribute giving Buildbot's base URL,
    # and ``static_url`` attribute giving Buildbot's static files URL

    @property
    def base_url(self) -> str:
        return self.master.config.buildbotURL

    def __init__(self, master: BuildMaster) -> None:
        super().__init__()
        self.master = master
        if self.needsReconfig and master is not None:
            master.www.resourceNeedsReconfigs(self)

    def reconfigResource(self, new_config: object) -> None:
        raise NotImplementedError

    def asyncRenderHelper(
        self,
        request: server.Request,
        _callable: Callable[[server.Request], _T],
        writeError: Callable[..., None] | None = None,
    ) -> int:
        def writeErrorDefault(msg: bytes, errcode: int = 400) -> None:
            request.setResponseCode(errcode)
            request.setHeader(b'content-type', b'text/plain; charset=utf-8')
            request.write(msg)
            request.finish()

        if writeError is None:
            writeError = writeErrorDefault
        try:
            d: defer.Deferred[Any] = defer.maybeDeferred(_callable, request)
        except Exception as e:
            d = defer.fail(e)

        @d.addCallback
        def finish(s: bytes | None) -> None:
            try:
                if s is not None:
                    request.write(s)
                request.finish()
            except RuntimeError:  # pragma: no cover
                # this occurs when the client has already disconnected; ignore
                # it (see #2027)
                log.msg("http client disconnected before results were sent")

        @d.addErrback
        def failHttpRedirect(f: defer.Failure) -> None:
            f.trap(Redirect)
            request.redirect(f.value.url)
            request.finish()
            return None

        @d.addErrback
        def failHttpError(f: defer.Failure) -> None:
            f.trap(Error)
            e = f.value
            message = unicode2bytes(e.message)
            writeError(message, errcode=int(e.status))

        @d.addErrback
        def fail(f: defer.Failure) -> None:
            log.err(f, 'While rendering resource:')
            try:
                writeError(b'internal error - see logs', errcode=500)
            except Exception:
                try:
                    request.finish()
                except Exception:
                    pass

        return server.NOT_DONE_YET


class RedirectResource(Resource):
    def __init__(self, master: BuildMaster, basepath: str) -> None:
        super().__init__(master)
        self.basepath = basepath

    def render(self, request: server.Request) -> str:
        redir = self.base_url + self.basepath
        request.redirect(protect_redirect_url(unicode2bytes(redir)))
        return redir

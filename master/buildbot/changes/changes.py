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

import html
import time
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.python import log

from buildbot import util
from buildbot.process.properties import Properties
from buildbot.util import datetime2epoch

if TYPE_CHECKING:
    from buildbot.db.changes import ChangeModel


class Change:
    """I represent a single change to the source tree. This may involve several
    files, but they are all changed by the same person, and there is a change
    comment for the group as a whole."""

    number: int | None = None
    branch: str | None = None
    category: str | None = None
    revision: str | None = None  # used to create a source-stamp
    links: list[str] = []  # links are gone, but upgrade code expects this attribute

    @classmethod
    def fromChdict(cls, master: Any, chdict: ChangeModel) -> Change:
        """
        Class method to create a L{Change} from a L{ChangeModel} as returned
        by L{ChangesConnectorComponent.getChange}.

        @param master: build master instance
        @param chdict: change model

        @returns: L{Change} via Deferred
        """
        cache = master.caches.get_cache("Changes", cls._make_ch)
        return cache.get(chdict.changeid, chdict=chdict, master=master)

    @classmethod
    def _make_ch(cls, changeid: int, master: Any, chdict: ChangeModel) -> defer.Deferred[Change]:
        change = cls(None, None, None, _fromChdict=True)
        change.who = chdict.author
        change.committer = chdict.committer
        change.comments = chdict.comments
        change.revision = chdict.revision
        change.branch = chdict.branch
        change.category = chdict.category
        change.revlink = chdict.revlink or ""
        change.repository = chdict.repository
        change.codebase = chdict.codebase
        change.project = chdict.project
        change.number = chdict.changeid

        when = chdict.when_timestamp
        if when:
            when = datetime2epoch(when)
        change.when = when

        change.files = sorted(chdict.files)

        change.properties = Properties()
        for n, (v, s) in chdict.properties.items():
            change.properties.setProperty(n, v, s)

        return defer.succeed(change)

    def __init__(
        self,
        who: str | None,
        files: list[str] | None,
        comments: str | None,
        committer: str | None = None,
        revision: str | None = None,
        when: int | None = None,
        branch: str | None = None,
        category: str | None = None,
        revlink: str = '',
        properties: dict[str, Any] | None = None,
        repository: str = '',
        codebase: str = '',
        project: str = '',
        _fromChdict: bool = False,
    ) -> None:
        if properties is None:
            properties = {}
        # skip all this madness if we're being built from the database
        if _fromChdict:
            return

        self.who = who
        self.committer = committer
        self.comments = comments

        def none_or_unicode(x: Any) -> str | None:
            if x is None:
                return x
            return str(x)

        self.revision = none_or_unicode(revision)
        now = util.now()
        if when is None:
            self.when = now
        elif when > now:
            # this happens when the committing system has an incorrect clock, for example.
            # handle it gracefully
            log.msg("received a Change with when > now; assuming the change happened now")
            self.when = now
        else:
            self.when = when
        self.branch = none_or_unicode(branch)
        self.category = none_or_unicode(category)
        self.revlink = revlink
        self.properties = Properties()
        self.properties.update(properties, "Change")
        self.repository = repository
        self.codebase = codebase
        self.project = project

        # keep a sorted list of the files, for easier display
        self.files = sorted(files or [])

    def __setstate__(self, dict: dict[str, Any]) -> None:
        self.__dict__ = dict
        # Older Changes won't have a 'properties' attribute in them
        if not hasattr(self, 'properties'):
            self.properties = Properties()
        if not hasattr(self, 'revlink'):
            self.revlink = ""

    def __str__(self) -> str:
        return (
            "Change(revision=%r, who=%r, committer=%r, branch=%r, comments=%r, "
            + "when=%r, category=%r, project=%r, repository=%r, "
            + "codebase=%r)"
        ) % (
            self.revision,
            self.who,
            self.committer,
            self.branch,
            self.comments,
            self.when,
            self.category,
            self.project,
            self.repository,
            self.codebase,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Change):
            raise NotImplementedError
        return self.number == other.number

    def __ne__(self, other: object) -> bool:
        if not isinstance(other, Change):
            raise NotImplementedError
        return self.number != other.number

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, Change):
            raise NotImplementedError
        if self.number is None:
            return False
        if other.number is None:
            return False
        return self.number < other.number

    def __le__(self, other: object) -> bool:
        if not isinstance(other, Change):
            raise NotImplementedError
        if self.number is None:
            return other.number is None
        if other.number is None:
            return False
        return self.number <= other.number

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, Change):
            raise NotImplementedError
        if self.number is None:
            return False
        if other.number is None:
            return False
        return self.number > other.number

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, Change):
            raise NotImplementedError
        if self.number is None:
            return other.number is None
        if other.number is None:
            return False
        return self.number >= other.number

    def asText(self) -> str:
        data = ""
        data += "Files:\n"
        for f in self.files:
            data += f" {f}\n"
        if self.repository:
            data += f"On: {self.repository}\n"
        if self.project:
            data += f"For: {self.project}\n"
        data += f"At: {self.getTime()}\n"
        data += f"Changed By: {self.who}\n"
        data += f"Committed By: {self.committer}\n"
        data += f"Comments: {self.comments}"
        data += "Properties: \n"
        for prop in self.properties.asList():
            data += f"  {prop[0]}: {prop[1]}"
        data += '\n\n'
        return data

    def asDict(self) -> dict[str, Any]:
        """returns a dictionary with suitable info for html/mail rendering"""
        files = [{"name": f} for f in self.files]
        files.sort(key=lambda a: a['name'])

        result = {
            # Constant
            'number': self.number,
            'branch': self.branch,
            'category': self.category,
            'who': self.getShortAuthor(),
            'committer': self.committer,
            'comments': self.comments,
            'revision': self.revision,
            'rev': self.revision,
            'when': self.when,
            'at': self.getTime(),
            'files': files,
            'revlink': getattr(self, 'revlink', None),
            'properties': self.properties.asList(),
            'repository': getattr(self, 'repository', None),
            'codebase': getattr(self, 'codebase', ''),
            'project': getattr(self, 'project', None),
        }
        return result

    def getShortAuthor(self) -> str | None:
        return self.who

    def getTime(self) -> str:
        if not self.when:
            return "?"
        return time.strftime("%a %d %b %Y %H:%M:%S", time.localtime(self.when))

    def getTimes(self) -> tuple[int | None, None]:
        return (self.when, None)

    def getText(self) -> list[str]:
        return [html.escape(self.who or "")]

    def getLogs(self) -> dict[str, Any]:
        return {}

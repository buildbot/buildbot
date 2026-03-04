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

from twisted.internet import defer
from zope.interface import implementer

from buildbot import interfaces
from buildbot.process.build import Build
from buildbot.process.buildrequest import BuildRequest
from buildbot.process.properties import Properties
from buildbot.process.results import CANCELLED
from buildbot.reporters import utils
from buildbot.reporters.message import MessageFormatterRenderable

from .utils import BuildStatusGeneratorMixin

if TYPE_CHECKING:
    from collections.abc import Sequence

    from buildbot.util.twisted import InlineCallbacksType


@implementer(interfaces.IReportGenerator)
class BuildRequestGenerator(BuildStatusGeneratorMixin):
    wanted_event_keys = [('buildrequests', None, 'new'), ('buildrequests', None, 'cancel')]

    compare_attrs: ClassVar[Sequence[str]] = ['formatter']

    def __init__(
        self,
        tags: list[str] | None = None,
        builders: list[str] | None = None,
        schedulers: list[str] | None = None,
        branches: list[str] | None = None,
        add_patch: bool = False,
        formatter: MessageFormatterRenderable | None = None,
    ) -> None:
        super().__init__('all', tags, builders, schedulers, branches, None, None, add_patch)
        self.formatter: MessageFormatterRenderable = formatter  # type: ignore[assignment]
        if self.formatter is None:
            self.formatter = MessageFormatterRenderable('Build pending.')

    @defer.inlineCallbacks
    def partial_build_dict(self, master: Any, buildrequest: Any) -> InlineCallbacksType[Any]:
        brdict = yield master.db.buildrequests.getBuildRequest(buildrequest['buildrequestid'])
        bdict = {}

        props = Properties()
        buildrequest = yield BuildRequest.fromBrdict(master, brdict)
        builder = yield master.botmaster.getBuilderById(brdict.builderid)

        yield Build.setup_properties_known_before_build_starts(props, [buildrequest], builder)
        Build.setupBuildProperties(props, [buildrequest])

        bdict['properties'] = props.asDict()
        yield utils.get_details_for_buildrequest(master, brdict, bdict)
        return bdict

    @defer.inlineCallbacks
    def generate(
        self, master: Any, reporter: Any, key: Any, buildrequest: Any
    ) -> InlineCallbacksType[Any]:
        build = yield self.partial_build_dict(master, buildrequest)
        _, _, event = key
        if event == 'cancel':
            build['complete'] = True
            build['results'] = CANCELLED

        if not self.is_message_needed_by_props(build):
            return None

        report = yield self.buildrequest_message(master, build)
        return report

    @defer.inlineCallbacks
    def buildrequest_message(self, master: Any, build: Any) -> InlineCallbacksType[Any]:
        patches = self._get_patches_for_build(build)
        users: list[Any] = []
        buildmsg = yield self.formatter.format_message_for_build(
            master, build, is_buildset=True, mode=self.mode, users=users
        )

        return {
            'body': buildmsg['body'],
            'subject': buildmsg['subject'],
            'type': buildmsg['type'],
            'results': build['results'],
            'builds': [build],
            "buildset": build["buildset"],
            'users': list(users),
            'patches': patches,
            'logs': [],
            "extra_info": buildmsg["extra_info"],
        }

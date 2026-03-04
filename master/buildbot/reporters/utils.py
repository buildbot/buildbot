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

import dataclasses
from collections import UserList
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.python import log

from buildbot.data import resultspec
from buildbot.process.properties import Properties
from buildbot.process.properties import renderer
from buildbot.process.results import RETRY
from buildbot.util import flatten

if TYPE_CHECKING:
    from buildbot.db.buildrequests import BuildRequestModel
    from buildbot.master import BuildMaster
    from buildbot.util.twisted import InlineCallbacksType


@defer.inlineCallbacks
def getPreviousBuild(
    master: BuildMaster, build: dict[str, Any]
) -> InlineCallbacksType[dict[str, Any] | None]:
    # naive n-1 algorithm. Still need to define what we should skip
    # SKIP builds? forced builds? rebuilds?
    # don't hesitate to contribute improvements to that algorithm
    n = build['number'] - 1
    while n >= 0:
        prev = yield master.data.get(("builders", build['builderid'], "builds", n))

        if prev and prev['results'] != RETRY:
            return prev
        n -= 1
    return None


@defer.inlineCallbacks
def getDetailsForBuildset(
    master: BuildMaster,
    bsid: int,
    want_properties: bool = False,
    want_steps: bool = False,
    want_previous_build: bool = False,
    want_logs: bool = False,
    add_logs: list[str] | bool | None = None,
    want_logs_content: bool | list[str] = False,
) -> InlineCallbacksType[dict[str, Any]]:
    # Here we will do a bunch of data api calls on behalf of the reporters
    # We do try to make *some* calls in parallel with the help of gatherResults, but don't commit
    # to much in that. The idea is to do parallelism while keeping the code readable
    # and maintainable.

    # first, just get the buildset and all build requests for our buildset id
    dl = [
        master.data.get(("buildsets", bsid)),
        master.data.get(
            ('buildrequests',), filters=[resultspec.Filter('buildsetid', 'eq', [bsid])]
        ),
    ]
    (buildset, breqs) = yield defer.gatherResults(dl, consumeErrors=True)
    # next, get the bdictlist for each build request
    dl = [master.data.get(("buildrequests", breq['buildrequestid'], 'builds')) for breq in breqs]

    builds = yield defer.gatherResults(dl, consumeErrors=True)
    flat_builds: list[dict[str, Any]] = list(flatten(builds, types=(list, UserList)))
    if flat_builds:
        yield getDetailsForBuilds(
            master,
            buildset,
            flat_builds,
            want_properties=want_properties,
            want_steps=want_steps,
            want_previous_build=want_previous_build,
            want_logs=want_logs,
            add_logs=add_logs,
            want_logs_content=want_logs_content,
        )

    return {"buildset": buildset, "builds": flat_builds}


@defer.inlineCallbacks
def getDetailsForBuild(
    master: BuildMaster,
    build: dict[str, Any],
    want_properties: bool = False,
    want_steps: bool = False,
    want_previous_build: bool = False,
    want_logs: bool = False,
    add_logs: list[str] | bool | None = None,
    want_logs_content: bool | list[str] = False,
) -> InlineCallbacksType[Any]:
    buildrequest = yield master.data.get(("buildrequests", build['buildrequestid']))
    buildset = yield master.data.get(("buildsets", buildrequest['buildsetid']))
    build['buildrequest'] = buildrequest
    build['buildset'] = buildset

    parentbuild = None
    parentbuilder = None
    if buildset['parent_buildid']:
        parentbuild = yield master.data.get(("builds", buildset['parent_buildid']))
        parentbuilder = yield master.data.get(("builders", parentbuild['builderid']))
    build['parentbuild'] = parentbuild
    build['parentbuilder'] = parentbuilder

    ret = yield getDetailsForBuilds(
        master,
        buildset,
        [build],
        want_properties=want_properties,
        want_steps=want_steps,
        want_previous_build=want_previous_build,
        want_logs=want_logs,
        add_logs=add_logs,
        want_logs_content=want_logs_content,
    )
    return ret


@defer.inlineCallbacks
def get_details_for_buildrequest(
    master: BuildMaster, buildrequest: BuildRequestModel, build: dict[str, Any]
) -> InlineCallbacksType[None]:
    buildset = yield master.data.get(("buildsets", buildrequest.buildsetid))
    builder = yield master.data.get(("builders", buildrequest.builderid))

    build['buildrequest'] = dataclasses.asdict(buildrequest)
    build['buildset'] = buildset
    build['builderid'] = buildrequest.builderid
    build['builder'] = builder
    build['url'] = getURLForBuildrequest(master, buildrequest.buildrequestid)
    build['results'] = None
    build['complete'] = False


def should_attach_log(logs_config: list[str] | bool, log: dict[str, Any]) -> bool:
    if isinstance(logs_config, bool):
        return logs_config

    if log['name'] in logs_config:
        return True

    long_name = f"{log['stepname']}.{log['name']}"
    if long_name in logs_config:
        return True

    return False


@defer.inlineCallbacks
def getDetailsForBuilds(
    master: BuildMaster,
    buildset: dict[str, Any],
    builds: list[dict[str, Any]],
    want_properties: bool = False,
    want_steps: bool = False,
    want_previous_build: bool = False,
    want_logs: bool = False,
    add_logs: list[str] | bool | None = None,
    want_logs_content: bool | list[str] = False,
) -> InlineCallbacksType[None]:
    builderids = {build['builderid'] for build in builds}

    builders = yield defer.gatherResults(
        [master.data.get(("builders", _id)) for _id in builderids], consumeErrors=True
    )

    buildersbyid = {builder['builderid']: builder for builder in builders}

    if want_properties:
        buildproperties = yield defer.gatherResults(
            [master.data.get(("builds", build['buildid'], 'properties')) for build in builds],
            consumeErrors=True,
        )
    else:  # we still need a list for the big zip
        buildproperties = list(range(len(builds)))

    if want_previous_build:
        prev_builds = yield defer.gatherResults(
            [getPreviousBuild(master, build) for build in builds], consumeErrors=True
        )
    else:  # we still need a list for the big zip
        prev_builds = list(range(len(builds)))

    if add_logs is not None:
        logs_config = add_logs
    elif want_logs_content is not None:
        logs_config = want_logs_content
    else:
        logs_config = False

    if logs_config is not False:
        want_logs = True
    if want_logs:
        want_steps = True

    if want_steps:  # pylint: disable=too-many-nested-blocks
        buildsteps = yield defer.gatherResults(
            [master.data.get(("builds", build['buildid'], 'steps')) for build in builds],
            consumeErrors=True,
        )
        if want_logs:
            for build, build_steps in zip(builds, buildsteps):
                for s in build_steps:
                    logs = yield master.data.get(("steps", s['stepid'], 'logs'))
                    s['logs'] = list(logs)
                    for l in s['logs']:
                        l['stepname'] = s['name']
                        l['url'] = get_url_for_log(
                            master, build['builderid'], build['number'], s['number'], l['slug']
                        )
                        l['url_raw'] = get_url_for_log_raw(master, l['logid'], 'raw')
                        l['url_raw_inline'] = get_url_for_log_raw(master, l['logid'], 'raw_inline')
                        if should_attach_log(logs_config, l):
                            l['content'] = yield master.data.get(("logs", l['logid'], 'contents'))

    else:  # we still need a list for the big zip
        buildsteps = list(range(len(builds)))

    # a big zip to connect everything together
    for build, properties, steps, prev in zip(builds, buildproperties, buildsteps, prev_builds):
        build['builder'] = buildersbyid[build['builderid']]
        build['buildset'] = buildset
        build['url'] = getURLForBuild(master, build['builderid'], build['number'])

        if want_properties:
            build['properties'] = properties

        if want_steps:
            build['steps'] = list(steps)

        if want_previous_build:
            build['prev_build'] = prev


# perhaps we need data api for users with sourcestamps/:id/users
@defer.inlineCallbacks
def getResponsibleUsersForSourceStamp(
    master: BuildMaster, sourcestampid: int
) -> InlineCallbacksType[list[str]]:
    changesd = master.data.get(("sourcestamps", sourcestampid, "changes"))
    sourcestampd = master.data.get(("sourcestamps", sourcestampid))
    changes, sourcestamp = yield defer.gatherResults([changesd, sourcestampd], consumeErrors=True)
    blamelist: set[str] = set()
    # normally, we get only one, but just assume there might be several
    for c in changes:
        blamelist.add(c['author'])
    # Add patch author to blamelist
    if 'patch' in sourcestamp and sourcestamp['patch'] is not None:
        blamelist.add(sourcestamp['patch']['author'])
    blamelist_sorted = list(blamelist)
    blamelist_sorted.sort()
    return blamelist_sorted


# perhaps we need data api for users with builds/:id/users
@defer.inlineCallbacks
def getResponsibleUsersForBuild(
    master: BuildMaster, buildid: int
) -> InlineCallbacksType[list[str]]:
    dl = [
        master.data.get(("builds", buildid, "changes")),
        master.data.get(("builds", buildid, 'properties')),
    ]
    changes, properties = yield defer.gatherResults(dl, consumeErrors=True)
    blamelist: set[str] = set()

    # add users from changes
    for c in changes:
        blamelist.add(c['author'])

    # add owner from properties
    if 'owner' in properties:
        owner = properties['owner'][0]
        if isinstance(owner, str):
            blamelist.add(owner)
        else:
            blamelist.update(owner)
            log.msg(f"Warning: owner property is a list for buildid {buildid}. ")
            log.msg(f"Please report a bug: changes: {changes}. properties: {properties}")

    # add owner from properties
    if 'owners' in properties:
        blamelist.update(properties['owners'][0])

    blamelist_sorted = list(blamelist)
    blamelist_sorted.sort()
    return blamelist_sorted


# perhaps we need data api for users with buildsets/:id/users
@defer.inlineCallbacks
def get_responsible_users_for_buildset(
    master: BuildMaster, buildsetid: int
) -> InlineCallbacksType[list[str]]:
    props = yield master.data.get(("buildsets", buildsetid, "properties"))

    # TODO: This currently does not track what changes were in the buildset. getChangesForBuild()
    # would walk the change graph until it finds last successful build and uses the authors of
    # the changes as blame list. Probably this needs to be done here too
    owner = props.get("owner", None)
    if owner:
        return [owner[0]]
    return []


def getURLForBuild(master: BuildMaster, builderid: int, build_number: int) -> str:
    prefix = master.config.buildbotURL
    return prefix + f"#/builders/{builderid}/builds/{build_number}"


def getURLForBuildrequest(master: BuildMaster, buildrequestid: int) -> str:
    prefix = master.config.buildbotURL
    return f"{prefix}#/buildrequests/{buildrequestid}"


def get_url_for_log(
    master: BuildMaster, builderid: int, build_number: int, step_number: int, log_slug: str
) -> str:
    prefix = master.config.buildbotURL
    return (
        f"{prefix}#/builders/{builderid}/builds/{build_number}/"
        + f"steps/{step_number}/logs/{log_slug}"
    )


def get_url_for_log_raw(master: BuildMaster, logid: int, suffix: str) -> str:
    prefix = master.config.buildbotURL
    return f"{prefix}api/v2/logs/{logid}/{suffix}"


@renderer
def URLForBuild(props: Properties) -> str:
    build = props.getBuild()
    return build.getUrl()


def merge_reports_prop(reports: list[dict[str, Any]], prop: str) -> Any:
    result = None
    for report in reports:
        if prop in report and report[prop] is not None:
            if result is None:
                result = report[prop]
            else:
                result += report[prop]

    return result


def merge_reports_prop_take_first(reports: list[dict[str, Any]], prop: str) -> Any:
    for report in reports:
        if prop in report and report[prop] is not None:
            return report[prop]

    return None

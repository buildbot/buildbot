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

from UserList import UserList
from buildbot.data import resultspec
from buildbot.process.results import RETRY
from buildbot.util import flatten
from twisted.internet import defer


@defer.inlineCallbacks
def getPreviousBuild(master, build):
    # naive n-1 algorithm. Still need to define what we should skip
    # SKIP builds? forced builds? rebuilds?
    # dont hesitate to contribute improvments to that algorithm
    n = build['number'] - 1
    while n >= 0:
        prev = yield master.data.get(("builders", build['builderid'], "builds", n))
        if prev['results'] != RETRY:
            defer.returnValue(prev)
        n -= 1
    defer.returnValue(None)


@defer.inlineCallbacks
def getDetailsForBuildset(master, bsid, wantProperties=False, wantSteps=False,
                          wantPreviousBuild=False, wantLogs=False):
    # Here we will do a bunch of data api calls on behalf of the reporters
    # We do try to make *some* calls in parallel with the help of gatherResults, but don't commit
    # to much in that. The idea is to do parallelism while keeping the code readable
    # and maintainable.

    # first, just get the buildset and all build requests for our buildset id
    dl = [master.data.get(("buildsets", bsid)),
          master.data.get(('buildrequests', ),
                          filters=[resultspec.Filter('buildsetid', 'eq', [bsid])])]
    (buildset, breqs) = yield defer.gatherResults(dl)
    # next, get the bdictlist for each build request
    dl = [master.data.get(("buildrequests", breq['buildrequestid'], 'builds'))
          for breq in breqs]

    builds = yield defer.gatherResults(dl)
    builds = flatten(builds, types=(list, UserList))
    if builds:
        yield getDetailsForBuilds(master, buildset, builds, wantProperties=wantProperties,
                                  wantSteps=wantSteps, wantPreviousBuild=wantPreviousBuild, wantLogs=wantLogs)

    defer.returnValue(dict(buildset=buildset, builds=builds))


@defer.inlineCallbacks
def getDetailsForBuilds(master, buildset, builds, wantProperties=False, wantSteps=False,
                        wantPreviousBuild=False, wantLogs=False):
    builderids = set([build['builderid'] for build in builds])

    builders = yield defer.gatherResults([master.data.get(("builders", _id))
                                          for _id in builderids])

    buildersbyid = dict([(builder['builderid'], builder) for builder in builders])

    if wantProperties:
        buildproperties = yield defer.gatherResults(
            [master.data.get(("builds", build['buildid'], 'properties'))
             for build in builds])
    else:  # we still need a list for the big zip
        buildproperties = range(len(builds))

    if wantPreviousBuild:
        prev_builds = yield defer.gatherResults(
            [getPreviousBuild(master, build) for build in builds])
    else:  # we still need a list for the big zip
        prev_builds = range(len(builds))

    if wantSteps:
        buildsteps = yield defer.gatherResults(
            [master.data.get(("builds", build['buildid'], 'steps'))
             for build in builds])
        if wantLogs:
            for s in flatten(buildsteps, types=(list, UserList)):
                s['logs'] = yield master.data.get(("steps", s['stepid'], 'logs'))
                for l in s['logs']:
                    l['content'] = yield master.data.get(("logs", l['logid'], 'contents'))

    else:  # we still need a list for the big zip
        buildsteps = range(len(builds))

    # a big zip to connect everything together
    for build, properties, steps, prev in zip(builds, buildproperties, buildsteps, prev_builds):
        build['builder'] = buildersbyid[build['builderid']]
        build['buildset'] = buildset
        if wantProperties:
            build['properties'] = properties

        if wantSteps:
            build['steps'] = steps

        if wantPreviousBuild:
            build['prev_build'] = prev


# perhaps we need data api for users with sourcestamps/:id/users
@defer.inlineCallbacks
def getResponsibleUsersForSourceStamp(master, sourcestampid):
    changesd = master.data.get(("sourcestamps", sourcestampid, "changes"))
    sourcestampd = master.data.get(("sourcestamps", sourcestampid))
    changes, sourcestamp = yield defer.gatherResults([changesd, sourcestampd])
    blamelist = set()
    # normally, we get only one, but just assume there might be several
    for c in changes:
        blamelist.add(c['author'])
    if 'patch' in sourcestamp and sourcestamp['patch'] is not None:  # Add patch author to blamelist
        blamelist.add(sourcestamp['patch']['author'])
    blamelist = list(blamelist)
    blamelist.sort()
    defer.returnValue(blamelist)


# perhaps we need data api for users with builds/:id/users
@defer.inlineCallbacks
def getResponsibleUsersForBuild(master, buildid):
    dl = [
        master.data.get(("builds", buildid, "changes")),
        master.data.get(("builds", buildid, 'properties'))
        ]
    changes, properties = yield defer.gatherResults(dl)
    blamelist = set()

    # add users from changes
    for c in changes:
        blamelist.add(c['author'])

    # add owner from properties
    if 'owner' in properties:
        blamelist.add(properties['owner'][0])

    blamelist = list(blamelist)
    blamelist.sort()
    defer.returnValue(blamelist)


def getURLForBuild(master, builderid, build_number):
    prefix = master.config.buildbotURL
    return prefix + "#builders/%d/builds/%d" % (
        builderid,
        build_number)

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

import operator
import re
import time
import urllib
import pprint
from twisted.internet import defer
from buildbot import util
from buildbot.changes import changes
from buildbot.status import builder
from buildbot.status.web.base import HtmlResource
from twisted.internet import defer


class DoesNotPassFilter(Exception):
    pass  # Used for filtering changes


def getResultsClass(results, prevResults, inProgress, inBuilder):
    """Given the current and past results, return the class that will be used
    by the css to display the right color for a box."""

    if inProgress:
        return "running"

    if results is None:
        if inBuilder:
            return "notstarted"
        else:
            return "notinbuilder"

    if results == builder.SUCCESS:
        return "success"

    if results == builder.WARNINGS:
        return "warnings"

    if results == builder.FAILURE:
        if not prevResults:
            # This is the bottom box. We don't know if the previous one failed
            # or not. We assume it did not.
            return "failure"

        if prevResults != builder.FAILURE:
            # This is a new failure.
            return "failure"
        else:
            # The previous build also failed.
            return "failure-again"

    # Any other results? Like EXCEPTION?
    return "exception"


class ANYBRANCH:
    pass  # a flag value, used below


class DevChange:
    """Helper class that contains all the information we need for a change."""

    def __init__(self, change):
        # unfortunately changes.Change.fromChdict renames changeid into number,
        # so we have to live with the confusion
        self.changeid = change.number
        self.revision = change.revision
        self.comments = change.comments
        self.who = change.who
        self.date = change.getTime()
        self.revlink = getattr(change, 'revlink', None)
        self.when = change.when
        self.repository = change.repository
        self.project = change.project


class DevBuild:

    """Helper class that contains all the information we need for a build."""

    def __init__(self, changeid, build, details):
        self.changeid = changeid
        for c in build.getChanges():
            if c.number == changeid:
                self.revision = c.revision
                break
        else:
            self.revision = None
        self.results =  build.getResults()
        self.number = build.getNumber()
        self.isFinished = build.isFinished()
        self.text = build.getText()
        self.eta = build.getETA()
        self.details = details
        self.when = build.getTimes()[0]
        self.sourceStamps = build.getSourceStamps()


class ConsoleStatusResource(HtmlResource):

    """Main console class. It displays a user-oriented status page.
    Every change is a line in the page, and it shows the result of the first
    build with this change for each slave."""

    def __init__(self):
        HtmlResource.__init__(self)
        self.status = None
        self.comparator = ChangeIdComparator()

    def getPageTitle(self, request):
        status = self.getStatus(request)
        title = status.getTitle()
        if title:
            return "BuildBot: %s" % title
        else:
            return "BuildBot"

    def getChangeManager(self, request):
        return request.site.buildbot_service.parent.change_svc

    #
    # Data gathering functions
    #

    def getHeadBuild(self, builder):
        """Get the most recent build for the given builder.
        """
        build = builder.getBuild(-1)

        # HACK: Work around #601, the head build may be None if it is
        # locked.
        if build is None:
            build = builder.getBuild(-2)

        return build

    def fetchChangesFromHistory(self, status, max_depth, max_builds, debugInfo):
        """Look at the history of the builders and try to fetch as many changes
        as possible. We need this when the main source does not contain enough
        sourcestamps.

        max_depth defines how many builds we will parse for a given builder.
        max_builds defines how many builds total we want to parse. This is to
            limit the amount of time we spend in this function.

        This function is sub-optimal, but the information returned by this
        function is cached, so this function won't be called more than once.
        """

        allChanges = list()
        build_count = 0
        for builderName in status.getBuilderNames()[:]:
            if build_count > max_builds:
                break

            builder = status.getBuilder(builderName)
            build = self.getHeadBuild(builder)
            depth = 0
            while build and depth < max_depth and build_count < max_builds:
                depth += 1
                build_count += 1
                sourcestamp = build.getSourceStamps()[0]
                allChanges.extend(sourcestamp.changes[:])
                build = build.getPreviousBuild()

        debugInfo["source_fetch_len"] = len(allChanges)
        return allChanges

    @defer.inlineCallbacks
    def getAllChanges(self, request, status, numChanges, debugInfo):
        master = request.site.buildbot_service.master

        chdicts = yield master.db.changes.getRecentChanges(numChanges)

        # convert those to Change instances
        allChanges = yield defer.gatherResults([
            changes.Change.fromChdict(master, chdict)
            for chdict in chdicts])

        allDevChanges = [DevChange(x) for x in allChanges]
        allDevChanges.sort(key=self.comparator.getSortingKey())

        defer.returnValue(allDevChanges)

    def getBuildDetails(self, request, builderName, build):
        """Returns an HTML list of failures for a given build."""
        details = {}
        if not build.getLogs():
            return details

        for step in build.getSteps():
            (result, reason) = step.getResults()
            if result == builder.FAILURE:
                name = step.getName()

                # Remove html tags from the error text.
                stripHtml = re.compile(r'<.*?>')
                strippedDetails = stripHtml.sub('', ' '.join(step.getText()))

                details['buildername'] = builderName
                details['status'] = strippedDetails
                details['reason'] = reason
                logs = details['logs'] = []

                if step.getLogs():
                    for log in step.getLogs():
                        logname = log.getName()
                        logurl = request.childLink(
                            "../builders/%s/builds/%s/steps/%s/logs/%s" %
                            (urllib.quote(builderName),
                             build.getNumber(),
                             urllib.quote(name),
                             urllib.quote(logname)))
                        logs.append(dict(url=logurl, name=logname))
        return details

    def getBuildsForChange(self, request, builder, builderName, codebase,
                           lastChangeId, numBuilds, debugInfo):
        """Return the list of all the builds for a given builder that we will
        need to be able to display the console page. We start by the most recent
        build, and we go down until we find a build that was built prior to the
        last change we are interested in."""

        builds = []
        build = self.getHeadBuild(builder)
        number = 0
        while build and number < numBuilds:
            debugInfo["builds_scanned"] += 1

            got_changeid = max([-1] + [c.number for c in build.changes])

            if got_changeid != -1:
                number += 1
                details = self.getBuildDetails(request, builderName, build)
                devBuild = DevBuild(got_changeid, build, details)
                builds.append(devBuild)

                # Now break if we have enough builds.
                current_change = self.getChangeForBuild(build, lastChangeId)
                if self.comparator.isChangeEarlier(devBuild, current_change):
                    break

            build = build.getPreviousBuild()

        return builds

    def getChangeForBuild(self, build, changeid):
        if not build or not build.getChanges(): # Forced build
            return DevBuild(changeid, build, None)

        for change in build.getChanges():
            if change.number == changeid:
                return DevChange(change)

        # No matching change, return the last change in build.
        changes = [DevChange(x) for x in build.getChanges()]
        changes.sort(key=self.comparator.getSortingKey())
        return changes[-1]

    def getAllBuildsForChangeId(self, status, request, codebase, lastChangeId,
                                numBuilds, categories, builders, debugInfo):
        """Returns a dictionary of builds we need to inspect to be able to
        display the console page. The key is the builder name, and the value is
        an array of build we care about. We also returns a dictionary of
        builders we care about. The key is it's category.

        codebase is the codebase to get revisions from
        lastRevision is the last revision we want to display in the page.
        categories is a list of categories to display. It is coming from the
            HTTP GET parameters.
        builders is a list of builders to display. It is coming from the HTTP
            GET parameters.
        """

        allBuilds = dict()

        # List of all builders in the dictionary.
        builderList = dict()

        debugInfo["builds_scanned"] = 0
        # Get all the builders.
        builderNames = status.getBuilderNames()[:]
        for builderName in builderNames:
            builder = status.getBuilder(builderName)

            # Make sure we are interested in this builder.
            if categories and builder.category not in categories:
                continue
            if builders and builderName not in builders:
                continue

            # We want to display this builder.
            category = builder.category or "default"
            # Strip the category to keep only the text before the first |.
            # This is a hack to support the chromium usecase where they have
            # multiple categories for each slave. We use only the first one.
            # TODO(nsylvain): Create another way to specify "display category"
            #     in master.cfg.
            category = category.split('|')[0]
            if not builderList.get(category):
                builderList[category] = []

            # Append this builder to the dictionary of builders.
            builderList[category].append(builderName)
            # Set the list of builds for this builder.
            allBuilds[builderName] = self.getBuildsForChange(request,
                                                             builder,
                                                             builderName,
                                                             codebase,
                                                             lastChangeId,
                                                             numBuilds,
                                                             debugInfo)

        return (builderList, allBuilds)

    #
    # Display functions
    #
    def displayCategories(self, builderList, debugInfo):
        """Display the top category line."""

        count = 0
        for category in builderList:
            count += len(builderList[category])

        categories = builderList.keys()
        categories.sort()

        cs = []

        for category in categories:
            c = {}

            c["name"] = category

            # To be able to align the table correctly, we need to know
            # what percentage of space this category will be taking. This is
            # (#Builders in Category) / (#Builders Total) * 100.
            c["size"] = (len(builderList[category]) * 100) / count
            cs.append(c)

        return cs

    def displaySlaveLine(self, status, builderList, debugInfo):
        """Display a line the shows the current status for all the builders we
        care about."""

        nbSlaves = 0

        # Get the number of builders.
        for category in builderList:
            nbSlaves += len(builderList[category])

        # Get the categories, and order them alphabetically.
        categories = sorted(builderList.keys())

        slaves = {}

        # For each category, we display each builder.
        for category in categories:
            slaves[category] = []
            # For each builder in this category, we set the build info and we
            # display the box.
            for bldr in builderList[category]:
                s = {}
                s["color"] = "notstarted"
                s["pageTitle"] = bldr
                s["url"] = "./builders/%s" % urllib.quote(bldr)
                state, builds = status.getBuilder(bldr).getState()
                # Check if it's offline, if so, the box is purple.
                if state == "offline":
                    s["color"] = "offline"
                else:
                    # If not offline, then display the result of the last
                    # finished build.
                    build = self.getHeadBuild(status.getBuilder(bldr))
                    while build and not build.isFinished():
                        build = build.getPreviousBuild()

                    if build:
                        s["color"] = getResultsClass(build.getResults(), None,
                                                     False, True)

                slaves[category].append(s)

        return slaves

    def displayStatusLine(self, builderList, allBuilds, change, debugInfo):
        """Display the boxes that represent the status of each builder in the
        first build "change" was in. Returns an HTML list of errors that
        happened during these builds."""

        details = []
        nbSlaves = 0
        for category in builderList:
            nbSlaves += len(builderList[category])

        # Sort the categories.
        categories = builderList.keys()
        categories.sort()

        builds = {}

        # Display the boxes by category group.
        for category in categories:

            builds[category] = []

            # Display the boxes for each builder in this category.
            for bldr in builderList[category]:
                introducedIn = None
                firstNotIn = None
                # If there is no builds default to True
                inBuilder = len(allBuilds[bldr]) == 0

                # Find the first build that does not include the change.
                for build in allBuilds[bldr]:
                    if self.comparator.isChangeEarlier(build, change):
                        firstNotIn = build
                        break
                    else:
                        introducedIn = build

                # Get the results of the first build with the change, and the
                # first build that does not include the change.
                results = None
                previousResults = None
                if introducedIn:
                    results = introducedIn.results
                if firstNotIn:
                    previousResults = firstNotIn.results

                isRunning = False
                if introducedIn and not introducedIn.isFinished:
                    isRunning = True

                url = "./waterfall"
                pageTitle = bldr
                tag = ""
                current_details = {}
                if introducedIn:
                    current_details = introducedIn.details or ""
                    url = "./buildstatus?builder=%s&amp;number=%s" % (urllib.quote(bldr),
                                                                      introducedIn.number)
                    pageTitle += " "
                    pageTitle += urllib.quote(' '.join(introducedIn.text), ' \n\\/:')

                    builderStrip = bldr.replace(' ', '')
                    builderStrip = builderStrip.replace('(', '')
                    builderStrip = builderStrip.replace(')', '')
                    builderStrip = builderStrip.replace('.', '')
                    tag = "Tag%s%s" % (builderStrip, introducedIn.number)

                if isRunning:
                    pageTitle += ' ETA: %ds' % (introducedIn.eta or 0)

                resultsClass = getResultsClass(results, previousResults, isRunning, True)

                b = {}
                b["url"] = url
                b["pageTitle"] = pageTitle
                b["color"] = resultsClass
                b["tag"] = tag

                builds[category].append(b)

                # If the box is red, we add the explaination in the details
                # section.
                if current_details and resultsClass == "failure":
                    details.append(current_details)

        return (builds, details)

    def filterChanges(self, changes, filter=None, max_changes=None):
        """Filter a set of changes based on any number of filter criteria.
        If specified, filter should be a dict with keys corresponding to
        change attributes, and values of 1+ strings"""
        if not filter:
            if max_changes is None:
                for change in reversed(changes):
                    yield change
            else:
                for index, change in enumerate(reversed(changes)):
                    if index >= max_changes:
                        break
                    yield change
        else:
            for index, change in enumerate(reversed(changes)):
                if max_changes and index >= max_changes:
                    break
                try:
                    for field, acceptable in filter.iteritems():
                        if not hasattr(change, field):
                            raise DoesNotPassFilter
                        if type(acceptable) in (str, unicode):
                            if getattr(change, field) != acceptable:
                                raise DoesNotPassFilter
                        elif type(acceptable) in (list, tuple, set):
                            if getattr(change, field) not in acceptable:
                                raise DoesNotPassFilter
                    yield change
                except DoesNotPassFilter:
                    pass

    def displayPage(self, request, status, builderList, allBuilds, codebase,
                    changes, categories, repository, project, branch,
                    debugInfo):
        """Display the console page."""
        # Build the main template directory with all the informations we have.
        subs = dict()
        subs["branch"] = branch or 'trunk'
        subs["repository"] = repository
        subs["project"] = project
        subs["codebase"] = codebase
        if categories:
            subs["categories"] = ' '.join(categories)
        subs["time"] = time.strftime("%a %d %b %Y %H:%M:%S",
                                     time.localtime(util.now()))
        subs["debugInfo"] = debugInfo
        subs["ANYBRANCH"] = ANYBRANCH

        if builderList:
            subs["categories"] = self.displayCategories(builderList, debugInfo)
            subs['slaves'] = self.displaySlaveLine(status, builderList, debugInfo)
        else:
            subs["categories"] = []

        subs['changes'] = []

        # For each change we show one line
        for change in changes:
            r = {}

            # Fill the dictionary with this new information
            r['id'] = change.revision
            r['link'] = change.revlink
            r['who'] = change.who
            r['date'] = change.date
            r['comments'] = change.comments
            r['repository'] = change.repository
            r['project'] = change.project

            # Display the status for all builders.
            (builds, details) = self.displayStatusLine(builderList,
                                            allBuilds,
                                            change,
                                            debugInfo)
            r['builds'] = builds
            r['details'] = details

            # Calculate the td span for the comment and the details.
            r["span"] = len(builderList) + 3

            subs['changes'].append(r)

        #
        # Display the footer of the page.
        #
        debugInfo["load_time"] = time.time() - debugInfo["load_time"]
        return subs

    def content(self, request, cxt):
        "This method builds the main console view display."

        reload_time = None
        # Check if there was an arg. Don't let people reload faster than
        # every 15 seconds. 0 means no reload.
        if "reload" in request.args:
            try:
                reload_time = int(request.args["reload"][0])
                if reload_time != 0:
                    reload_time = max(reload_time, 15)
            except ValueError:
                pass

        request.setHeader('Cache-Control', 'no-cache')

        # Sets the default reload time to 60 seconds.
        if not reload_time:
            reload_time = 60

        # Append the tag to refresh the page.
        if reload_time is not None and reload_time != 0:
            cxt['refresh'] = reload_time

        # Debug information to display at the end of the page.
        debugInfo = cxt['debuginfo'] = dict()
        debugInfo["load_time"] = time.time()

        # get url parameters
        # Categories to show information for.
        categories = request.args.get("category", [])
        # List of all builders to show on the page.
        builders = request.args.get("builder", [])
        # Repo used to filter the changes shown.
        repository = request.args.get("repository", [None])[0]
        # Project used to filter the changes shown.
        project = request.args.get("project", [None])[0]
        # Branch used to filter the changes shown.
        branch = request.args.get("branch", [ANYBRANCH])[0]
        # Codebase used to filter the changes shown.
        codebase = request.args.get("codebase", [None])[0]
        # List of all the committers name to display on the page.
        devName = request.args.get("name", [])

        # and the data we want to render
        status = self.getStatus(request)

        # Keep only the changes we care about.
        # By default we process the last 40 changes.
        # If a dev name is passed, we look for the last 80 changes by this
        # person.
        numChanges = int(request.args.get("changes", [40])[0])
        if devName:
            numChanges *= 2
        numBuilds = numChanges

        # Get all changes we can find.  This is a DB operation, so it must use
        # a deferred.
        d = self.getAllChanges(request, status, numChanges, debugInfo)

        def got_changes(allChanges):
            debugInfo["source_all"] = len(allChanges)

            changeFilter = {}
            if branch != ANYBRANCH:
                changeFilter['branch'] = branch
            if devName:
                changeFilter['who'] = devName
            if repository:
                changeFilter['repository'] = repository
            if project:
                changeFilter['project'] = project
            if codebase is not None:
                changeFilter['codebase'] = codebase
            changes = list(self.filterChanges(allChanges,
                                              max_changes=numChanges,
                                              filter=changeFilter))
            debugInfo["change_final"] = len(changes)

            # Fetch all the builds for all builders until we get the next build
            # after lastChangeId.
            builderList = None
            allBuilds = None
            if changes:
                lastChangeId = changes[len(changes) - 1].changeid
                debugInfo["last_changeid"] = lastChangeId

                (builderList, allBuilds) = self.getAllBuildsForChangeId(status,
                                                    request,
                                                    codebase,
                                                    lastChangeId,
                                                    numBuilds,
                                                    categories,
                                                    builders,
                                                    debugInfo)

            debugInfo["added_blocks"] = 0

            cxt.update(self.displayPage(request, status, builderList,
                                        allBuilds, codebase, changes,
                                        categories, repository, project,
                                        branch, debugInfo))
            cxt['debuginfo'] = pprint.pformat(debugInfo,
                indent=4).replace('\n','<br />').replace('    ', '&nbsp;' * 4)

            templates = request.site.buildbot_service.templates
            template = templates.get_template("console.html")
            data = template.render(cxt)
            return data
        d.addCallback(got_changes)
        return d

class ChangeIdComparator(object):
    def isChangeEarlier(self, first, second):
        return first.changeid < second.changeid

    def getSortingKey(self):
        return operator.attrgetter('changeid')

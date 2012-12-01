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

import time
import operator
import re
import urllib
from twisted.internet import defer
from buildbot import util
from buildbot.status import builder
from buildbot.status.web.base import HtmlResource
from buildbot.changes import changes

class DoesNotPassFilter(Exception): pass # Used for filtering revs

def getResultsClass(results, prevResults, inProgress):
    """Given the current and past results, return the class that will be used
    by the css to display the right color for a box."""

    if inProgress:
        return "running"

    if results is None:
        return "notstarted"

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

class ANYBRANCH: pass # a flag value, used below

class DevRevision:
    """Helper class that contains all the information we need for a revision."""

    def __init__(self, change):
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

    def __init__(self, revision, build, details):
        self.revision = revision
        self.results =  build.getResults()
        self.number = build.getNumber()
        self.isFinished = build.isFinished()
        self.text = build.getText()
        self.eta = build.getETA()
        self.details = details
        self.when = build.getTimes()[0]
        #TODO: support multiple sourcestamps
        self.source = build.getSourceStamps()[0]


class ConsoleStatusResource(HtmlResource):
    """Main console class. It displays a user-oriented status page.
    Every change is a line in the page, and it shows the result of the first
    build with this change for each slave."""

    def __init__(self, orderByTime=False):
        HtmlResource.__init__(self)

        self.status = None

        if orderByTime:
            self.comparator = TimeRevisionComparator()
        else:
            self.comparator = IntegerRevisionComparator()

    def getPageTitle(self, request):
        status = self.getStatus(request)
        title = status.getTitle()
        if title:
            return "BuildBot: %s" % title
        else:
            return "BuildBot"

    def getChangeManager(self, request):
        return request.site.buildbot_service.parent.change_svc

    ##
    ## Data gathering functions
    ##

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
    def getAllChanges(self, request, status, debugInfo):
        master = request.site.buildbot_service.master

        chdicts = yield master.db.changes.getRecentChanges(25)

        # convert those to Change instances
        allChanges = yield defer.gatherResults([
                changes.Change.fromChdict(master, chdict)
                for chdict in chdicts ])

        allChanges.sort(key=self.comparator.getSortingKey())

        # Remove the dups
        prevChange = None
        newChanges = []
        for change in allChanges:
            rev = change.revision
            if not prevChange or rev != prevChange.revision:
                newChanges.append(change)
            prevChange = change
        allChanges = newChanges

        defer.returnValue(allChanges)

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

    def getBuildsForRevision(self, request, builder, builderName, codebase,
                             lastRevision, numBuilds, debugInfo):
        """Return the list of all the builds for a given builder that we will
        need to be able to display the console page. We start by the most recent
        build, and we go down until we find a build that was built prior to the
        last change we are interested in."""

        revision = lastRevision 

        builds = []
        build = self.getHeadBuild(builder)
        number = 0
        while build and number < numBuilds:
            debugInfo["builds_scanned"] += 1

            got_rev = None
            sourceStamps = build.getSourceStamps(absolute=True)

            # The console page cannot handle builds that have more than 1 revision
            if codebase is not None:
                # Get the last revision in this build for this codebase.
                for ss in sourceStamps:
                    if ss.codebase == codebase:
                        got_rev = ss.revision
                        break
            elif len(sourceStamps) == 1:
                ss = sourceStamps[0]
                # Get the last revision in this build.
                got_rev = ss.revision
                    
            # We ignore all builds that don't have last revisions.
            # TODO(nsylvain): If the build is over, maybe it was a problem
            # with the update source step. We need to find a way to tell the
            # user that his change might have broken the source update.
            if got_rev is not None:
                number += 1
                details = self.getBuildDetails(request, builderName, build)
                devBuild = DevBuild(got_rev, build, details)
                builds.append(devBuild)

                # Now break if we have enough builds.
                current_revision = self.getChangeForBuild(
                    build, revision)
                if self.comparator.isRevisionEarlier(
                    devBuild, current_revision):
                    break

            build = build.getPreviousBuild()

        return builds

    def getChangeForBuild(self, build, revision):
        if not build or not build.getChanges(): # Forced build
            return DevBuild(revision, build, None)
        
        for change in build.getChanges():
            if change.revision == revision:
                return change

        # No matching change, return the last change in build.
        changes = list(build.getChanges())
        changes.sort(key=self.comparator.getSortingKey())
        return changes[-1]
    
    def getAllBuildsForRevision(self, status, request, codebase, lastRevision,
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
            allBuilds[builderName] = self.getBuildsForRevision(request,
                                                               builder,
                                                               builderName,
                                                               codebase,
                                                               lastRevision,
                                                               numBuilds,
                                                               debugInfo)

        return (builderList, allBuilds)


    ##
    ## Display functions
    ##

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
        categories = builderList.keys()
        categories.sort()

        slaves = {}

        # For each category, we display each builder.
        for category in categories:
            slaves[category] = []
            # For each builder in this category, we set the build info and we
            # display the box.
            for builder in builderList[category]:
                s = {}
                s["color"] = "notstarted"
                s["pageTitle"] = builder
                s["url"] = "./builders/%s" % urllib.quote(builder)
                state, builds = status.getBuilder(builder).getState()
                # Check if it's offline, if so, the box is purple.
                if state == "offline":
                    s["color"] = "offline"
                else:
                    # If not offline, then display the result of the last
                    # finished build.
                    build = self.getHeadBuild(status.getBuilder(builder))
                    while build and not build.isFinished():
                        build = build.getPreviousBuild()

                    if build:
                        s["color"] = getResultsClass(build.getResults(), None,
                                                      False)

                slaves[category].append(s)

        return slaves

    def displayStatusLine(self, builderList, allBuilds, revision, debugInfo):
        """Display the boxes that represent the status of each builder in the
        first build "revision" was in. Returns an HTML list of errors that
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
            for builder in builderList[category]:
                introducedIn = None
                firstNotIn = None

                # Find the first build that does not include the revision.
                for build in allBuilds[builder]:
                    if self.comparator.isRevisionEarlier(build, revision):
                        firstNotIn = build
                        break
                    else:
                        introducedIn = build
                        
                # Get the results of the first build with the revision, and the
                # first build that does not include the revision.
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
                pageTitle = builder
                tag = ""
                current_details = {}
                if introducedIn:
                    current_details = introducedIn.details or ""
                    url = "./buildstatus?builder=%s&number=%s" % (urllib.quote(builder),
                                                                  introducedIn.number)
                    pageTitle += " "
                    pageTitle += urllib.quote(' '.join(introducedIn.text), ' \n\\/:')

                    builderStrip = builder.replace(' ', '')
                    builderStrip = builderStrip.replace('(', '')
                    builderStrip = builderStrip.replace(')', '')
                    builderStrip = builderStrip.replace('.', '')
                    tag = "Tag%s%s" % (builderStrip, introducedIn.number)

                if isRunning:
                    pageTitle += ' ETA: %ds' % (introducedIn.eta or 0)
                    
                resultsClass = getResultsClass(results, previousResults, isRunning)

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

    def filterRevisions(self, revisions, filter=None, max_revs=None):
        """Filter a set of revisions based on any number of filter criteria.
        If specified, filter should be a dict with keys corresponding to
        revision attributes, and values of 1+ strings"""
        if not filter:
            if max_revs is None:
                for rev in reversed(revisions):
                    yield DevRevision(rev)
            else:
                for index,rev in enumerate(reversed(revisions)):
                    if index >= max_revs:
                        break
                    yield DevRevision(rev)
        else:
            for index, rev in enumerate(reversed(revisions)):
                if max_revs and index >= max_revs:
                    break
                try:
                    for field,acceptable in filter.iteritems():
                        if not hasattr(rev, field):
                            raise DoesNotPassFilter
                        if type(acceptable) in (str, unicode):
                            if getattr(rev, field) != acceptable:
                                raise DoesNotPassFilter
                        elif type(acceptable) in (list, tuple, set):
                            if getattr(rev, field) not in acceptable:
                                raise DoesNotPassFilter
                    yield DevRevision(rev)
                except DoesNotPassFilter:
                    pass

    def displayPage(self, request, status, builderList, allBuilds, codebase,
                    revisions, categories, repository, project, branch,
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

        subs['revisions'] = []

        # For each revision we show one line
        for revision in revisions:
            r = {}
            
            # Fill the dictionary with this new information
            r['id'] = revision.revision
            r['link'] = revision.revlink 
            r['who'] = revision.who
            r['date'] = revision.date
            r['comments'] = revision.comments
            r['repository'] = revision.repository
            r['project'] = revision.project

            # Display the status for all builders.
            (builds, details) = self.displayStatusLine(builderList,
                                            allBuilds,
                                            revision,
                                            debugInfo)
            r['builds'] = builds
            r['details'] = details

            # Calculate the td span for the comment and the details.
            r["span"] = len(builderList) + 2            

            subs['revisions'].append(r)

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

        # Keep only the revisions we care about.
        # By default we process the last 40 revisions.
        # If a dev name is passed, we look for the changes by this person in the
        # last 80 revisions.
        numRevs = int(request.args.get("revs", [40])[0])
        if devName:
            numRevs *= 2
        numBuilds = numRevs

        # Get all changes we can find.  This is a DB operation, so it must use
        # a deferred.
        d = self.getAllChanges(request, status, debugInfo)
        def got_changes(allChanges):
            debugInfo["source_all"] = len(allChanges)

            revFilter = {}
            if branch != ANYBRANCH:
                revFilter['branch'] = branch
            if devName:
                revFilter['who'] = devName
            if repository:
                revFilter['repository'] = repository
            if project:
                revFilter['project'] = project
            if codebase is not None:
                revFilter['codebase'] = codebase
            revisions = list(self.filterRevisions(allChanges, max_revs=numRevs,
                                                            filter=revFilter))
            debugInfo["revision_final"] = len(revisions)

            # Fetch all the builds for all builders until we get the next build
            # after lastRevision.
            builderList = None
            allBuilds = None
            if revisions:
                lastRevision = revisions[len(revisions) - 1].revision
                debugInfo["last_revision"] = lastRevision

                (builderList, allBuilds) = self.getAllBuildsForRevision(status,
                                                    request,
                                                    codebase,
                                                    lastRevision,
                                                    numBuilds,
                                                    categories,
                                                    builders,
                                                    debugInfo)

            debugInfo["added_blocks"] = 0

            cxt.update(self.displayPage(request, status, builderList,
                                        allBuilds, codebase, revisions,
                                        categories, repository, project,
                                        branch, debugInfo))

            templates = request.site.buildbot_service.templates
            template = templates.get_template("console.html")
            data = template.render(cxt)
            return data
        d.addCallback(got_changes)
        return d

class RevisionComparator(object):
    """Used for comparing between revisions, as some
    VCS use a plain counter for revisions (like SVN)
    while others use different concepts (see Git).
    """
    
    # TODO (avivby): Should this be a zope interface?
    
    def isRevisionEarlier(self, first_change, second_change):
        """Used for comparing 2 changes"""
        raise NotImplementedError

    def isValidRevision(self, revision):
        """Checks whether the revision seems like a VCS revision"""
        raise NotImplementedError

    def getSortingKey(self):
        raise NotImplementedError
    
class TimeRevisionComparator(RevisionComparator):
    def isRevisionEarlier(self, first, second):
        return first.when < second.when

    def isValidRevision(self, revision):
        return True # No general way of determining

    def getSortingKey(self):
        return operator.attrgetter('when')

class IntegerRevisionComparator(RevisionComparator):
    def isRevisionEarlier(self, first, second):
        try:
            return int(first.revision) < int(second.revision)
        except (TypeError, ValueError):
            return False

    def isValidRevision(self, revision):
        try:
            int(revision)
            return True
        except:
            return False

    def getSortingKey(self):
        return operator.attrgetter('revision')


from __future__ import generators

import time
import operator
import re
import urllib

from buildbot import util
from buildbot import version
from buildbot.status import builder
from buildbot.status.web.base import HtmlResource
from buildbot.status.web import console_html as res
from buildbot.status.web import console_js as js

def getResultsClass(results, prevResults, inProgress):
    """Given the current and past results, return the class that will be used
    by the css to display the right color for a box."""

    if inProgress:
        return "running"

    if results is None:
       return "notstarted"

    if results == builder.SUCCESS:
        return "success"

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
            return "warnings"
  
    # Any other results? Like EXCEPTION?
    return "exception"

class ANYBRANCH: pass # a flag value, used below

class DevRevision:
    """Helper class that contains all the information we need for a revision."""

    def __init__(self, revision, who, comments, date, revlink, when):
        self.revision = revision
        self.comments = comments
        self.who = who
        self.date = date
        self.revlink = revlink
        self.when = when


class DevBuild:
    """Helper class that contains all the information we need for a build."""

    def __init__(self, revision, results, number, isFinished, text, eta, details, when):
        self.revision = revision
        self.results = results 
        self.number = number
        self.isFinished = isFinished
        self.text = text
        self.eta = eta
        self.details = details
        self.when = when


class ConsoleStatusResource(HtmlResource):
    """Main console class. It displays a user-oriented status page.
    Every change is a line in the page, and it shows the result of the first
    build with this change for each slave."""

    def __init__(self, allowForce=True, css=None, orderByTime=False):
        HtmlResource.__init__(self)

        self.status = None
        self.control = None
        self.changemaster = None
        self.initialRevs = None

        self.allowForce = allowForce
        self.css = css

        if orderByTime:
            self.comparator = TimeRevisionComparator()
        else:
            self.comparator = IntegerRevisionComparator()

    def getTitle(self, request):
        status = self.getStatus(request)
        projectName = status.getProjectName()
        if projectName:
            return "BuildBot: %s" % projectName
        else:
            return "BuildBot"

    def getChangemaster(self, request):
        return request.site.buildbot_service.parent.change_svc

    def head(self, request):
        # Start by adding all the javascript functions we have.
        head = "<script type='text/javascript'> %s </script>" % js.JAVASCRIPT

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

        # Sets the default reload time to 60 seconds.
        if not reload_time:
            reload_time = 60

        # Append the tag to refresh the page. 
        if reload_time is not None and reload_time != 0:
            head += '<meta http-equiv="refresh" content="%d">\n' % reload_time
        return head


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
                sourcestamp = build.getSourceStamp()
                allChanges.extend(sourcestamp.changes[:])
                build = build.getPreviousBuild()

        debugInfo["source_fetch_len"] = len(allChanges)
        return allChanges                
        
    def getAllChanges(self, source, status, debugInfo):
        """Return all the changes we can find at this time. If |source| does not
        not have enough (less than 25), we try to fetch more from the builders
        history."""

        allChanges = list()
        allChanges.extend(source.changes[:])

        debugInfo["source_len"] = len(source.changes)

        if len(allChanges) < 25:
            # There is not enough revisions in the source.changes. It happens
            # quite a lot because buildbot mysteriously forget about changes
            # once in a while during restart.
            # Let's try to get more changes from the builders.
            # We check the last 10 builds of all builders, and stop when we
            # are done, or have looked at 100 builds.
            # We do this only once!
            if not self.initialRevs:
                self.initialRevs = self.fetchChangesFromHistory(status, 10, 100,
                                                                debugInfo)

            allChanges.extend(self.initialRevs)

            # the new changes are not sorted, and can contain duplicates.
            # Sort the list.
            allChanges.sort(lambda a, b: cmp(getattr(a, self.comparator.getSortingKey()), getattr(b, self.comparator.getSortingKey())))

            # Remove the dups
            prevChange = None
            newChanges = []
            for change in allChanges:
                rev = change.revision
                if not prevChange or rev != prevChange.revision:
                    newChanges.append(change)
                prevChange = change
            allChanges = newChanges

        return allChanges

    def stripRevisions(self, allChanges, numRevs, branch, devName):
        """Returns a subset of changesn from allChanges that matches the query.

        allChanges is the list of all changes we know about.
        numRevs is the number of changes we will inspect from allChanges. We
            do not want to inspect all of them or it would be too slow.
        branch is the branch we are interested in. Changes not in this branch
            will be ignored.
        devName is the developper name. Changes have not been submitted by this
            person will be ignored.
        """
        
        revisions = []

        if not allChanges:
            return revisions

        totalRevs = len(allChanges)
        for i in range(totalRevs-1, totalRevs-numRevs, -1):
            if i < 0:
                break
            change = allChanges[i]
            if branch == ANYBRANCH or branch == change.branch:
                if not devName or change.who in devName:
                    
                    rev = DevRevision(change.revision, change.who,
                                      change.comments, change.getTime(),
                                      getattr(change, 'revlink', None),
                                      change.when)
                    revisions.append(rev)

        return revisions

    def getBuildDetails(self, request, builderName, build):
        """Returns an HTML list of failures for a given build."""
        details = ""
        if build.getLogs():
            for step in build.getSteps():
                (result, reason) = step.getResults()
                if result == builder.FAILURE:
                  name = step.getName()

                  # Remove html tags from the error text.
                  stripHtml = re.compile(r'<.*?>')
                  strippedDetails = stripHtml .sub('', ' '.join(step.getText()))

                  details += "<li> %s : %s. \n" % (builderName, strippedDetails)
                  if step.getLogs():
                      details += "[ "
                      for log in step.getLogs():
                          logname = log.getName()
                          logurl = request.childLink(
                              "../builders/%s/builds/%s/steps/%s/logs/%s" %
                                (urllib.quote(builderName),
                                 build.getNumber(),
                                 urllib.quote(name),
                                 urllib.quote(logname)))
                          details += "<a href=\"%s\">%s</a> " % (logurl,
                                                                 log.getName())
                      details += "]"
        return details

    def getBuildsForRevision(self, request, builder, builderName, lastRevision,
                             numBuilds, debugInfo):
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
            number += 1

            # Get the last revision in this build.
            # We first try "got_revision", but if it does not work, then
            # we try "revision".
            got_rev = -1
            try:
                got_rev = build.getProperty("got_revision")
                if not self.comparator.isValidRevision(got_rev):
                    got_rev = -1
            except KeyError:
                pass

            try:
                if got_rev == -1:
                   got_rev = build.getProperty("revision")
                if not self.comparator.isValidRevision(got_rev):
                    got_rev = -1
            except:
                pass

            # We ignore all builds that don't have last revisions.
            # TODO(nsylvain): If the build is over, maybe it was a problem
            # with the update source step. We need to find a way to tell the
            # user that his change might have broken the source update.
            if got_rev and got_rev != -1:
                details = self.getBuildDetails(request, builderName, build)
                devBuild = DevBuild(got_rev, build.getResults(),
                                             build.getNumber(),
                                             build.isFinished(),
                                             build.getText(),
                                             build.getETA(),
                                             details,
                                             build.getTimes()[0])

                builds.append(devBuild)

                # Now break if we have enough builds.
                current_revision = self.getChangeForBuild(
                    builder.getBuild(-1), revision)
                if self.comparator.isRevisionEarlier(
                    devBuild, current_revision):
                    break

            build = build.getPreviousBuild()

        return builds

    def getChangeForBuild(self, build, revision):
        if not build.getChanges(): # Forced build
            devBuild = DevBuild(revision, build.getResults(),
                                build.getNumber(),
                                build.isFinished(),
                                build.getText(),
                                build.getETA(),
                                None,
                                build.getTimes()[0])

            return devBuild
        
        for change in build.getChanges():
            if change.revision == revision:
                return change

        # No matching change, return the last change in build.
        changes = list(build.getChanges())
        changes.sort(lambda a, b: cmp(getattr(a, self.comparator.getSortingKey()), getattr(b, self.comparator.getSortingKey())))
        return changes[-1]
    
    def getAllBuildsForRevision(self, status, request, lastRevision, numBuilds,
                                categories, builders, debugInfo):
        """Returns a dictionnary of builds we need to inspect to be able to
        display the console page. The key is the builder name, and the value is
        an array of build we care about. We also returns a dictionnary of
        builders we care about. The key is it's category.
 
        lastRevision is the last revision we want to display in the page.
        categories is a list of categories to display. It is coming from the
            HTTP GET parameters.
        builders is a list of builders to display. It is coming from the HTTP
            GET parameters.
        """

        allBuilds = dict()

        # List of all builders in the dictionnary.
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

            # Append this builder to the dictionnary of builders.
            builderList[category].append(builderName)
            # Set the list of builds for this builder.
            allBuilds[builderName] = self.getBuildsForRevision(request,
                                                               builder,
                                                               builderName,
                                                               lastRevision,
                                                               numBuilds,
                                                               debugInfo)

        return (builderList, allBuilds)


    ##
    ## Display functions
    ##

    def displayCategories(self, builderList, debugInfo, subs):
        """Display the top category line."""

        data = res.main_line_category_header.substitute(subs)
        count = 0
        for category in builderList:
            count += len(builderList[category])

        i = 0
        categories = builderList.keys()
        categories.sort()
        for category in categories:
            # First, we add a flag to say if it's the first or the last one.
            # This is useful is your css is doing rounding at the edge of the
            # tables.
            subs["first"] = ""
            subs["last"] = ""
            if i == 0:
                subs["first"] = "first"
            if i == len(builderList) -1:
                subs["last"] = "last"

            # TODO(nsylvain): Another hack to display the category in a pretty
            # way.  If the master owner wants to display the categories in a
            # given order, he/she can prepend a number to it. This number won't
            # be shown.
            subs["category"] = category.lstrip('0123456789')

            # To be able to align the table correctly, we need to know
            # what percentage of space this category will be taking. This is
            # (#Builders in Category) / (#Builders Total) * 100.
            subs["size"] = (len(builderList[category]) * 100) / count
            data += res.main_line_category_name.substitute(subs)
            i += 1
        data += res.main_line_category_footer.substitute(subs)
        return data

    def displaySlaveLine(self, status, builderList, debugInfo, subs):
        """Display a line the shows the current status for all the builders we
        care about."""

        data = ""

        # Display the first TD (empty) element.
        subs["last"] = ""
        if len(builderList) == 1:
          subs["last"] = "last"
        data += res.main_line_slave_header.substitute(subs)

        nbSlaves = 0
        subs["first"] = ""

        # Get the number of builders.
        for category in builderList:
            nbSlaves += len(builderList[category])

        i = 0

        # Get the catefories, and order them alphabetically.
        categories = builderList.keys()
        categories.sort()

        # For each category, we display each builder.
        for category in categories:
            subs["last"] = ""

            # If it's the last category, we set the "last" flag.
            if i == len(builderList) - 1:
                subs["last"] = "last"

            # This is not the first category, we need to add the spacing we have
            # between 2 categories.
            if i != 0:
                data += res.main_line_slave_section.substitute(subs)

            i += 1

            # For each builder in this category, we set the build info and we
            # display the box.
            for builder in builderList[category]:
              subs["color"] = "notstarted"
              subs["title"] = builder
              subs["url"] = "./builders/%s" % urllib.quote(builder)
              state, builds = status.getBuilder(builder).getState()
              # Check if it's offline, if so, the box is purple.
              if state == "offline":
                  subs["color"] = "exception"
              else:
                  # If not offline, then display the result of the last
                  # finished build.
                  build = self.getHeadBuild(status.getBuilder(builder))
                  while build and not build.isFinished():
                      build = build.getPreviousBuild()

                  if build:
                      subs["color"] = getResultsClass(build.getResults(), None,
                                                      False)

              data += res.main_line_slave_status.substitute(subs)

        data += res.main_line_slave_footer.substitute(subs)
        return data

    def displayStatusLine(self, builderList, allBuilds, revision, debugInfo,
                          subs):
        """Display the boxes that represent the status of each builder in the
        first build "revision" was in. Returns an HTML list of errors that
        happened during these builds."""

        data = ""

        # Display the first TD (empty) element.
        subs["last"] = ""
        if len(builderList) == 1:
          subs["last"] = "last"
        data += res.main_line_status_header.substitute(subs)

        details = ""
        nbSlaves = 0
        subs["first"] = ""
        for category in builderList:
            nbSlaves += len(builderList[category])

        i = 0
        # Sort the categories.
        categories = builderList.keys()
        categories.sort()
  
        # Display the boxes by category group.
        for category in categories:
            # Last category? We set the "last" flag.
            subs["last"] = ""
            if i == len(builderList) - 1:
                subs["last"] = "last"

            # Not the first category? We add the spacing between 2 categories.
            if i != 0:
                data += res.main_line_status_section.substitute(subs)
            i += 1

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
                title = builder
                tag = ""
                current_details = None
                if introducedIn:
                    current_details = introducedIn.details or ""
                    url = "./buildstatus?builder=%s&number=%s" % (urllib.quote(builder),
                                                                  introducedIn.number)
                    title += " "
                    title += urllib.quote(' '.join(introducedIn.text), ' \n\\/:')

                    builderStrip = builder.replace(' ', '')
                    builderStrip = builderStrip.replace('(', '')
                    builderStrip = builderStrip.replace(')', '')
                    builderStrip = builderStrip.replace('.', '')
                    tag = "Tag%s%s" % (builderStrip, introducedIn.number)

                if isRunning:
                    title += ' ETA: %ds' % (introducedIn.eta or 0)

                resultsClass = getResultsClass(results, previousResults, isRunning)
                subs["url"] = url
                subs["title"] = title
                subs["color"] = resultsClass
                subs["tag"] = tag

                data += res.main_line_status_box.substitute(subs)

                # If the box is red, we add the explaination in the details
                # section.
                if current_details and resultsClass == "failure":
                    details += current_details

        data += res.main_line_status_footer.substitute(subs)
        return (data, details)

    def displayPage(self, request, status, builderList, allBuilds, revisions,
                    categories, branch, debugInfo):
        """Display the console page."""
        # Build the main template directory with all the informations we have.
        subs = dict()
        subs["projectUrl"] = status.getProjectURL() or ""
        subs["projectName"] = status.getProjectName() or ""
        subs["branch"] = branch or 'trunk'
        if categories:
            subs["categories"] = ' '.join(categories)
        subs["welcomeUrl"] = self.path_to_root(request) + "index.html"
        subs["version"] = version
        subs["time"] = time.strftime("%a %d %b %Y %H:%M:%S",
                                     time.localtime(util.now()))
        subs["debugInfo"] = debugInfo


        #
        # Show the header.
        #

        data = res.top_header.substitute(subs)
        data += res.top_info_name.substitute(subs)

        if categories:
            data += res.top_info_categories.substitute(subs)

        if branch != ANYBRANCH:
            data += res.top_info_branch.substitute(subs)

        data += res.top_info_name_end.substitute(subs)
        # Display the legend.
        data += res.top_legend.substitute(subs)

        # Display the personalize box.
        data += res.top_personalize.substitute(subs)

        data += res.top_footer.substitute(subs)


        #
        # Display the main page
        #
        data += res.main_header.substitute(subs)

        # "Alt" is set for every other line, to be able to switch the background
        # color.
        subs["alt"] = "Alt"
        subs["first"] = ""
        subs["last"] = ""

        # Display the categories if there is more than 1.
        if builderList and len(builderList) > 1:
            dataToAdd = self.displayCategories(builderList, debugInfo, subs)
            data += dataToAdd

        # Display the build slaves status.
        if builderList:
            dataToAdd = self.displaySlaveLine(status, builderList, debugInfo,
                                              subs)
            data += dataToAdd

        # For each revision we show one line
        for revision in revisions:
            if not subs["alt"]:
              subs["alt"] = "Alt"
            else:
              subs["alt"] = ""

            # Fill the dictionnary with these new information
            subs["revision"] = revision.revision
            if revision.revlink:
                subs["revision_link"] = ("<a href=\"%s\">%s</a>" 
                                         % (revision.revlink,
                                            revision.revision))
            else:
                subs["revision_link"] = revision.revision
            subs["who"] = revision.who
            subs["date"] = revision.date
            comment = revision.comments or ""
            subs["comments"] = comment.replace('<', '&lt;').replace('>', '&gt;')
            comment_quoted = urllib.quote(subs["comments"].encode("utf-8"))

            # Display the revision number and the committer.
            data += res.main_line_info.substitute(subs)

            # Display the status for all builders.
            (dataToAdd, details) = self.displayStatusLine(builderList,
                                                            allBuilds,
                                                            revision,
                                                            debugInfo,
                                                            subs)
            data += dataToAdd

            # Calculate the td span for the comment and the details.
            subs["span"] = len(builderList) + 2
            
            # Display the details of the failures, if any.
            if details:
              subs["details"] = details
              data += res.main_line_details.substitute(subs)

            # Display the comments for this revision
            data += res.main_line_comments.substitute(subs)

        data += res.main_footer.substitute(subs)

        #
        # Display the footer of the page.
        #
        debugInfo["load_time"] = time.time() - debugInfo["load_time"]
        data += res.bottom.substitute(subs)
        return data

    def body(self, request):
        "This method builds the main console view display."

        # Debug information to display at the end of the page.
        debugInfo = dict()
        debugInfo["load_time"] = time.time()

        # get url parameters
        # Categories to show information for.
        categories = request.args.get("category", [])
        # List of all builders to show on the page.
        builders = request.args.get("builder", [])
        # Branch used to filter the changes shown.
        branch = request.args.get("branch", [ANYBRANCH])[0]
        # List of all the committers name to display on the page.
        devName = request.args.get("name", [])

        # and the data we want to render
        status = self.getStatus(request)

        projectURL = status.getProjectURL()
        projectName = status.getProjectName()

        # Get all revisions we can find.
        source = self.getChangemaster(request)
        allChanges = self.getAllChanges(source, status, debugInfo)

        debugInfo["source_all"] = len(allChanges)

        # Keep only the revisions we care about.
        # By default we process the last 40 revisions.
        # If a dev name is passed, we look for the changes by this person in the
        # last 80 revisions.
        numRevs = 40
        if devName:
          numRevs *= 2
        numBuilds = numRevs


        revisions = self.stripRevisions(allChanges, numRevs, branch, devName)
        debugInfo["revision_final"] = len(revisions)

        # Fetch all the builds for all builders until we get the next build
        # after lastRevision.
        builderList = None
        allBuilds = None
        if revisions:
            lastRevision = revisions[len(revisions)-1].revision
            debugInfo["last_revision"] = lastRevision

            (builderList, allBuilds) = self.getAllBuildsForRevision(status,
                                                request,
                                                lastRevision,
                                                numBuilds,
                                                categories,
                                                builders,
                                                debugInfo)

        debugInfo["added_blocks"] = 0

        data = ""
        data += self.displayPage(request, status, builderList, allBuilds,
                                revisions, categories, branch, debugInfo)

        return data

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
        return "when"

class IntegerRevisionComparator(RevisionComparator):
    def isRevisionEarlier(self, first, second):
        return int(first.revision) < int(second.revision)

    def isValidRevision(self, revision):
        try:
            int(revision)
            return True
        except:
            return False

    def getSortingKey(self):
        return "revision"


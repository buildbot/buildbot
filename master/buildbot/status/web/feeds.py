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

# This module enables ATOM and RSS feeds from webstatus.
#
# It is based on "feeder.py" which was part of the Buildbot
# configuration for the Subversion project. The original file was
# created by Lieven Gobaerts and later adjusted by API
# (apinheiro@igalia.coma) and also here
# http://code.google.com/p/pybots/source/browse/trunk/master/Feeder.py
#
# All subsequent changes to feeder.py where made by Chandan-Dutta
# Chowdhury <chandan-dutta.chowdhury @ hp.com> and Gareth Armstrong
# <gareth.armstrong @ hp.com>.
#
# Those modifications are as follows:
# 1) the feeds are usable from baseweb.WebStatus
# 2) feeds are fully validated ATOM 1.0 and RSS 2.0 feeds, verified
#    with code from http://feedvalidator.org
# 3) nicer xml output
# 4) feeds can be filtered as per the /waterfall display with the
#    builder and category filters
# 5) cleaned up white space and imports
#
# Finally, the code was directly integrated into these two files,
# buildbot/status/web/feeds.py (you're reading it, ;-)) and
# buildbot/status/web/baseweb.py.

import os
import re
import time
from twisted.web import resource
from buildbot.status.builder import FAILURE

class XmlResource(resource.Resource):
    contentType = "text/xml; charset=UTF-8"
    docType = ''

    def getChild(self, name, request):
        return self

    def render(self, request):
        data = self.content(request)
        request.setHeader("content-type", self.contentType)
        if request.method == "HEAD":
            request.setHeader("content-length", len(data))
            return ''
        return data

_abbr_day = [ 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
_abbr_mon = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug',
            'Sep', 'Oct', 'Nov', 'Dec']

def rfc822_time(tstamp):
    res = time.strftime("%%s, %d %%s %Y %H:%M:%S GMT",
                                       tstamp)
    res = res % (tstamp.tm_wday, tstamp.tm_mon)
    return res

class FeedResource(XmlResource):
    pageTitle = None
    link = 'http://dummylink'
    language = 'en-us'
    description = 'Dummy rss'
    status = None

    def __init__(self, status, categories=None, pageTitle=None):
        self.status = status
        self.categories = categories
        self.pageTitle = pageTitle
        self.title = self.status.getTitle()
        self.link = self.status.getBuildbotURL()
        self.description = 'List of builds'
        self.pubdate = time.gmtime(int(time.time()))
        self.user = self.getEnv(['USER', 'USERNAME'], 'buildmaster')
        self.hostname = self.getEnv(['HOSTNAME', 'COMPUTERNAME'],
                                    'buildmaster')
        self.children = {}

    def getEnv(self, keys, fallback):
        for key in keys:
            if key in os.environ:
                return os.environ[key]
        return fallback

    def getBuilds(self, request):
        builds = []
        # THIS is lifted straight from the WaterfallStatusResource Class in
        # status/web/waterfall.py
        #
        # we start with all Builders available to this Waterfall: this is
        # limited by the config-file -time categories= argument, and defaults
        # to all defined Builders.
        allBuilderNames = self.status.getBuilderNames(categories=self.categories)
        builders = [self.status.getBuilder(name) for name in allBuilderNames]

        # but if the URL has one or more builder= arguments (or the old show=
        # argument, which is still accepted for backwards compatibility), we
        # use that set of builders instead. We still don't show anything
        # outside the config-file time set limited by categories=.
        showBuilders = request.args.get("show", [])
        showBuilders.extend(request.args.get("builder", []))
        if showBuilders:
            builders = [b for b in builders if b.name in showBuilders]

        # now, if the URL has one or category= arguments, use them as a
        # filter: only show those builders which belong to one of the given
        # categories.
        showCategories = request.args.get("category", [])
        if showCategories:
            builders = [b for b in builders if b.category in showCategories]

        failures_only = request.args.get("failures_only", "false")

        maxFeeds = 25

        # Copy all failed builds in a new list.
        # This could clearly be implemented much better if we had
        # access to a global list of builds.
        for b in builders:
            lastbuild = b.getLastFinishedBuild()
            if lastbuild is None:
                continue

            lastnr = lastbuild.getNumber()

            totalbuilds = 0
            i = lastnr
            while i >= 0:
                build = b.getBuild(i)
                i -= 1
                if not build:
                    continue

                results = build.getResults()

                if failures_only == "false" or results == FAILURE:
                    totalbuilds += 1
                    builds.append(build)

                # stop for this builder when our total nr. of feeds is reached
                if totalbuilds >= maxFeeds:
                    break

        # Sort build list by date, youngest first.
        # To keep compatibility with python < 2.4, use this for sorting instead:
        # We apply Decorate-Sort-Undecorate
        deco = [(build.getTimes(), build) for build in builds]
        deco.sort()
        deco.reverse()
        builds = [build for (b1, build) in deco]

        if builds:
            builds = builds[:min(len(builds), maxFeeds)]
        return builds

    def content(self, request):
        builds = self.getBuilds(request)

        build_cxts = []

        for build in builds:
            start, finished = build.getTimes()
            finishedTime = time.gmtime(int(finished))
            link = re.sub(r'index.html', "", self.status.getURLForThing(build))

            # title: trunk r22191 (plus patch) failed on
            # 'i686-debian-sarge1 shared gcc-3.3.5'
            ss = build.getSourceStamp()
            source = ""
            if ss.branch:
                source += "Branch %s " % ss.branch
            if ss.revision:
                source += "Revision %s " % str(ss.revision)
            if ss.patch:
                source += " (plus patch)"
            if ss.changes:
                pass
            if (ss.branch is None and ss.revision is None and ss.patch is None
                and not ss.changes):
                source += "Latest revision "
            got_revision = None
            try:
                got_revision = build.getProperty("got_revision")
            except KeyError:
                pass
            if got_revision:
                got_revision = str(got_revision)
                if len(got_revision) > 40:
                    got_revision = "[revision string too long]"
                source += "(Got Revision: %s)" % got_revision
            failflag = (build.getResults() != FAILURE)
            pageTitle = ('%s %s on "%s"' %
                     (source, ["failed","succeeded"][failflag],
                      build.getBuilder().getName()))

            # Add information about the failing steps.
            failed_steps = []
            log_lines = []
            for s in build.getSteps():
                if s.getResults()[0] == FAILURE:
                    failed_steps.append(s.getName())

                    # Add the last 30 lines of each log.
                    for log in s.getLogs():
                        log_lines.append('Last lines of build log "%s":' %
                                         log.getName())
                        log_lines.append([])
                        try:
                            logdata = log.getText()
                        except IOError:
                            # Probably the log file has been removed
                            logdata ='** log file not available **'
                        unilist = list()
                        for line in logdata.split('\n')[-30:]:
                            unilist.append(unicode(line,'utf-8'))
                        log_lines.extend(unilist)

            bc = {}
            bc['date'] = rfc822_time(finishedTime)
            bc['summary_link'] = ('%sbuilders/%s' %
                                  (self.link,
                                   build.getBuilder().getName()))            
            bc['name'] = build.getBuilder().getName()
            bc['number'] = build.getNumber()
            bc['responsible_users'] = build.getResponsibleUsers()
            bc['failed_steps'] = failed_steps
            bc['pageTitle'] = pageTitle
            bc['link'] = link
            bc['log_lines'] = log_lines

            if finishedTime is not None:
                bc['rfc822_pubdate'] = rfc822_time(finishedTime)
                bc['rfc3339_pubdate'] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                               finishedTime)

                # Every RSS/Atom item must have a globally unique ID
                guid = ('tag:%s@%s,%s:%s' %
                        (self.user, self.hostname,
                         time.strftime("%Y-%m-%d", finishedTime),
                         time.strftime("%Y%m%d%H%M%S", finishedTime)))
                bc['guid'] = guid

            build_cxts.append(bc)

        pageTitle = self.pageTitle
        if not pageTitle:
            pageTitle = 'Build status of %s' % self.pageTitle

        cxt = {}
        cxt['pageTitle'] = pageTitle
        cxt['title_url'] = self.link
        cxt['title'] = self.title
        cxt['language'] = self.language
        cxt['description'] = self.description
        if self.pubdate is not None:
            cxt['rfc822_pubdate'] = rfc822_time( self.pubdate)
            cxt['rfc3339_pubdate'] = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                   self.pubdate)

        cxt['builds'] = build_cxts
        template = request.site.buildbot_service.templates.get_template(self.template_file)
        return template.render(**cxt).encode('utf-8').strip()

class Rss20StatusResource(FeedResource):
    # contentType = 'application/rss+xml' (browser dependent)
    template_file = 'feed_rss20.xml'

    def __init__(self, status, categories=None, pageTitle=None):
        FeedResource.__init__(self, status, categories, pageTitle)

class Atom10StatusResource(FeedResource):
    # contentType = 'application/atom+xml' (browser dependent)
    template_file = 'feed_atom10.xml'

    def __init__(self, status, categories=None, pageTitle=None):
        FeedResource.__init__(self, status, categories, pageTitle)

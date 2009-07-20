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
import sys
import time
from twisted.web import resource, html
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, EXCEPTION

class XmlResource(resource.Resource):
    contentType = "text/xml; charset=UTF-8"
    def render(self, request):
        data = self.content(request)
        request.setHeader("content-type", self.contentType)
        if request.method == "HEAD":
            request.setHeader("content-length", len(data))
            return ''
        return data
    docType = ''
    def header (self, request):
        data = ('<?xml version="1.0"?>\n')
        return data
    def footer(self, request):
        data = ''
        return data
    def content(self, request):
        data = self.docType
        data += self.header(request)
        data += self.body(request)
        data += self.footer(request)
        return data
    def body(self, request):
        return ''

class FeedResource(XmlResource):
    title = None
    link = 'http://dummylink'
    language = 'en-us'
    description = 'Dummy rss'
    status = None

    def __init__(self, status, categories=None, title=None):
        self.status = status
        self.categories = categories
        self.title = title
        self.projectName = self.status.getProjectName()
        self.link = self.status.getBuildbotURL()
        self.description = 'List of FAILED builds'
        self.pubdate = time.gmtime(int(time.time()))
        self.user = self.getEnv(['USER', 'USERNAME'], 'buildmaster')
        self.hostname = self.getEnv(['HOSTNAME', 'COMPUTERNAME'],
                                    'buildmaster')

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

                # only add entries for failed builds!
                if results == FAILURE:
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

    def body (self, request):
        data = ''
        builds = self.getBuilds(request)

        for build in builds:
            start, finished = build.getTimes()
            finishedTime = time.gmtime(int(finished))
            link = re.sub(r'index.html', "", self.status.getURLForThing(build))

            # title: trunk r22191 (plus patch) failed on 'i686-debian-sarge1 shared gcc-3.3.5'
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
            title = ('%s failed on "%s"' %
                     (source, build.getBuilder().getName()))

            description = ''
            description += ('Date: %s<br/><br/>' %
                            time.strftime("%a, %d %b %Y %H:%M:%S GMT",
                                          finishedTime))
            description += ('Full details available here: <a href="%s">%s</a><br/>' %
                            (self.link, self.projectName))
            builder_summary_link = ('%s/builders/%s' %
                                    (re.sub(r'/index.html', '', self.link),
                                     build.getBuilder().getName()))
            description += ('Build summary: <a href="%s">%s</a><br/><br/>' %
                            (builder_summary_link,
                             build.getBuilder().getName()))
            description += ('Build details: <a href="%s">%s</a><br/><br/>' %
                            (link, link))
            description += ('Author list: <b>%s</b><br/><br/>' %
                            ",".join(build.getResponsibleUsers()))

            # Add information about the failing steps.
            lastlog = ''
            for s in build.getSteps():
                if s.getResults()[0] == FAILURE:
                    description += ('Failed step: <b>%s</b><br/>' % s.getName())

                    # Add the last 30 lines of each log.
                    for log in s.getLogs():
                        lastlog += ('Last lines of build log "%s":<br/>' % log.getName())
                        try:
                            logdata = log.getText()
                        except IOError:
                            # Probably the log file has been removed
                            logdata ='<b>log file not available</b>'

                        lastlines = logdata.split('\n')[-30:]
                        lastlog += '<br/>'.join(lastlines)
                        lastlog += '<br/>'
            description += '<br/>'

            data += self.item(title, description=description, lastlog=lastlog,
                              link=link, pubDate=finishedTime)

        return data

    def item(self, title='', link='', description='', pubDate=''):
        """Generates xml for one item in the feed."""

class Rss20StatusResource(FeedResource):
    def __init__(self, status, categories=None, title=None):
        FeedResource.__init__(self, status, categories, title)
        contentType = 'application/rss+xml'

    def header(self, request):
        data = FeedResource.header(self, request)
        data += ('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">\n')
        data += ('  <channel>\n')
        if self.title is None:
            title = 'Build status of ' + self.projectName
        else:
            title = self.title
        data += ('    <title>%s</title>\n' % title)
        if self.link is not None:
            data += ('    <link>%s</link>\n' % self.link)
        link = re.sub(r'/index.html', '', self.link)
        data += ('    <atom:link href="%s/rss" rel="self" type="application/rss+xml"/>\n' % link)
        if self.language is not None:
            data += ('    <language>%s</language>\n' % self.language)
        if self.description is not None:
            data += ('    <description>%s</description>\n' % self.description)
        if self.pubdate is not None:
            rfc822_pubdate = time.strftime("%a, %d %b %Y %H:%M:%S GMT",
                                           self.pubdate)
            data += ('    <pubDate>%s</pubDate>\n' % rfc822_pubdate)
        return data

    def item(self, title='', link='', description='', lastlog='', pubDate=''):
        data = ('      <item>\n')
        data += ('        <title>%s</title>\n' % title)
        if link is not None:
            data += ('        <link>%s</link>\n' % link)
        if (description is not None and lastlog is not None):
            lastlog = lastlog.replace('<br/>', '\n')
            lastlog = html.escape(lastlog)
            lastlog = lastlog.replace('\n', '<br/>')
            content = '<![CDATA['
            content += description
            content += lastlog
            content += ']]>'
            data += ('        <description>%s</description>\n' % content)
        if pubDate is not None:
            rfc822pubDate = time.strftime("%a, %d %b %Y %H:%M:%S GMT",
                                          pubDate)
            data += ('        <pubDate>%s</pubDate>\n' % rfc822pubDate)
            # Every RSS item must have a globally unique ID
            guid = ('tag:%s@%s,%s:%s' % (self.user, self.hostname,
                                         time.strftime("%Y-%m-%d", pubDate),
                                         time.strftime("%Y%m%d%H%M%S",
                                                       pubDate)))
            data += ('    <guid isPermaLink="false">%s</guid>\n' % guid)
        data += ('      </item>\n')
        return data

    def footer(self, request):
        data = ('  </channel>\n'
                '</rss>')
        return data

class Atom10StatusResource(FeedResource):
    def __init__(self, status, categories=None, title=None):
        FeedResource.__init__(self, status, categories, title)
        contentType = 'application/atom+xml'

    def header(self, request):
        data = FeedResource.header(self, request)
        data += '<feed xmlns="http://www.w3.org/2005/Atom">\n'
        data += ('  <id>%s</id>\n' % self.link)
        if self.title is None:
            title = 'Build status of ' + self.projectName
        else:
            title = self.title
        data += ('  <title>%s</title>\n' % title)
        if self.link is not None:
            link = re.sub(r'/index.html', '', self.link)
            data += ('  <link rel="self" href="%s/atom"/>\n' % link)
            data += ('  <link rel="alternate" href="%s/"/>\n' % link)
        if self.description is not None:
            data += ('  <subtitle>%s</subtitle>\n' % self.description)
        if self.pubdate is not None:
            rfc3339_pubdate = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                            self.pubdate)
            data += ('  <updated>%s</updated>\n' % rfc3339_pubdate)
        data += ('  <author>\n')
        data += ('    <name>Build Bot</name>\n')
        data += ('  </author>\n')
        return data

    def item(self, title='', link='', description='', lastlog='', pubDate=''):
        data = ('  <entry>\n')
        data += ('    <title>%s</title>\n' % title)
        if link is not None:
            data += ('    <link href="%s"/>\n' % link)
        if (description is not None and lastlog is not None):
            lastlog = lastlog.replace('<br/>', '\n')
            lastlog = html.escape(lastlog)
            lastlog = lastlog.replace('\n', '<br/>')
            data += ('    <content type="xhtml">\n')
            data += ('      <div xmlns="http://www.w3.org/1999/xhtml">\n')
            data += ('        %s\n' % description)
            data += ('        <pre xml:space="preserve">%s</pre>\n' % lastlog)
            data += ('      </div>\n')
            data += ('    </content>\n')
        if pubDate is not None:
            rfc3339pubDate = time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                           pubDate)
            data += ('    <updated>%s</updated>\n' % rfc3339pubDate)
            # Every Atom entry must have a globally unique ID
            # http://diveintomark.org/archives/2004/05/28/howto-atom-id
            guid = ('tag:%s@%s,%s:%s' % (self.user, self.hostname,
                                         time.strftime("%Y-%m-%d", pubDate),
                                         time.strftime("%Y%m%d%H%M%S",
                                                       pubDate)))
            data += ('    <id>%s</id>\n' % guid)
        data += ('    <author>\n')
        data += ('      <name>Build Bot</name>\n')
        data += ('    </author>\n')
        data += ('  </entry>\n')
        return data

    def footer(self, request):
        data = ('</feed>')
        return data

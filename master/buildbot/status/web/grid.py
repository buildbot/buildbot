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

from buildbot import util
from buildbot.sourcestamp import SourceStamp
from buildbot.status.web.base import HtmlResource
from buildbot.status.web.base import build_get_class
from buildbot.status.web.base import path_to_build
from buildbot.status.web.base import path_to_builder
from twisted.internet import defer


class ANYBRANCH:
    pass  # a flag value, used below


class GridStatusMixin(object):

    def getPageTitle(self, request):
        status = self.getStatus(request)
        p = status.getTitle()
        if p:
            return "BuildBot: %s" % p
        else:
            return "BuildBot"

    # handle reloads through an http header
    # TODO: send this as a real header, rather than a tag
    def get_reload_time(self, request):
        if "reload" in request.args:
            try:
                reload_time = int(request.args["reload"][0])
                return max(reload_time, 15)
            except ValueError:
                pass
        return None

    def build_cxt(self, request, build):
        if not build:
            return {}

        if build.isFinished():
            # get the text and annotate the first line with a link
            text = build.getText()
            if not text:
                text = ["(no information)"]
            if text == ["build", "successful"]:
                text = ["OK"]
        else:
            text = ['building']

        name = build.getBuilder().getName()

        cxt = {}
        cxt['name'] = name
        cxt['url'] = path_to_build(request, build)
        cxt['text'] = text
        cxt['class'] = build_get_class(build)
        return cxt

    @defer.inlineCallbacks
    def builder_cxt(self, request, builder):
        state, builds = builder.getState()

        # look for upcoming builds. We say the state is "waiting" if the
        # builder is otherwise idle and there is a scheduler which tells us a
        # build will be performed some time in the near future. TODO: this
        # functionality used to be in BuilderStatus.. maybe this code should
        # be merged back into it.
        upcoming = []
        builderName = builder.getName()
        for s in self.getStatus(request).getSchedulers():
            if builderName in s.listBuilderNames():
                upcoming.extend(s.getPendingBuildTimes())
        if state == "idle" and upcoming:
            state = "waiting"

        n_pending = len((yield builder.getPendingBuildRequestStatuses()))

        cxt = {'url': path_to_builder(request, builder),
               'name': builder.getName(),
               'tags': builder.tags,
               'state': state,
               'n_pending': n_pending}

        defer.returnValue(cxt)

    def getSourceStampKey(self, sourcestamps):
        """Given two source stamps, we want to assign them to the same row if
        they are the same version of code, even if they differ in minor detail.

        This function returns an appropriate comparison key for that.
        """
        # TODO: Maybe order sourcestamps in key by codebases names?
        return tuple([(ss.branch, ss.revision, ss.patch, ss.codebase,
                       ss.project) for ss in sourcestamps])

    def clearRecentBuildsCache(self):
        self.__recentBuildsCache__ = {}

    def getRecentBuilds(self, builder, numBuilds, branch):
        cache = getattr(self, '__recentBuildsCache__', {})
        key = (builder.getName(), branch, numBuilds)
        try:
            return cache[key]
        except KeyError:
            # cache miss, get the value and store it in the cache
            result = [b for b in self.__getRecentBuilds(builder, numBuilds, branch)]
            cache[key] = result
            return result

    def __getRecentBuilds(self, builder, numBuilds, branch):
        """
        get a list of most recent builds on given builder
        """
        build = builder.getBuild(-1)
        num = 0
        while build and num < numBuilds:
            start = build.getTimes()[0]
            # TODO: support multiple sourcestamps
            ss = build.getSourceStamps(absolute=True)[0]

            okay_build = True

            # skip un-started builds
            if not start:
                okay_build = False

            # skip non-matching branches
            if branch != ANYBRANCH and ss.branch != branch:
                okay_build = False

            if okay_build:
                num += 1
                yield build

            build = build.getPreviousBuild()
        return

    def getRecentSourcestamps(self, status, numBuilds, tags, branch):
        """
        get a list of the most recent NUMBUILDS SourceStamp tuples, sorted
        by the earliest start we've seen for them
        """
        # TODO: use baseweb's getLastNBuilds?
        sourcestamps = {}  # { ss-tuple : earliest time }
        for bn in status.getBuilderNames():
            builder = status.getBuilder(bn)
            if tags and not builder.matchesAnyTag(tags):
                continue
            for build in self.getRecentBuilds(builder, numBuilds, branch):
                ss = build.getSourceStamps(absolute=True)
                key = self.getSourceStampKey(ss)
                start = build.getTimes()[0]
                if key not in sourcestamps or sourcestamps[key][1] > start:
                    sourcestamps[key] = (ss, start)

        # now sort those and take the NUMBUILDS most recent
        sourcestamps = sorted(sourcestamps.itervalues(), key=lambda stamp: stamp[1])
        sourcestamps = [stamp[0] for stamp in sourcestamps][-numBuilds:]

        return sourcestamps


class GridStatusResource(HtmlResource, GridStatusMixin):
    # TODO: docs
    status = None
    changemaster = None

    @defer.inlineCallbacks
    def content(self, request, cxt):
        """This method builds the regular grid display.
        That is, build stamps across the top, build hosts down the left side
        """

        # get url parameters
        numBuilds = int(request.args.get("width", [5])[0])
        tags = request.args.get("tag", [])
        if not tags:
            tags = request.args.get("category", [])
        branch = request.args.get("branch", [ANYBRANCH])[0]
        if branch == 'trunk':
            branch = None

        # and the data we want to render
        status = self.getStatus(request)
        stamps = self.getRecentSourcestamps(status, numBuilds, tags, branch)

        cxt['refresh'] = self.get_reload_time(request)

        cxt.update({'tags': tags,
                    'branch': branch,
                    'ANYBRANCH': ANYBRANCH,
                    'stamps': [map(SourceStamp.asDict, sstamp) for sstamp in stamps],
                    })

        sortedBuilderNames = util.naturalSort(status.getBuilderNames())

        cxt['builders'] = []

        for bn in sortedBuilderNames:
            builds = [None] * len(stamps)

            builder = status.getBuilder(bn)
            if tags and not builder.matchesAnyTag(tags):
                continue

            for build in self.getRecentBuilds(builder, numBuilds, branch):
                ss = build.getSourceStamps(absolute=True)
                key = self.getSourceStampKey(ss)

                for i, sstamp in enumerate(stamps):
                    if key == self.getSourceStampKey(sstamp) and builds[i] is None:
                        builds[i] = build

            b = yield self.builder_cxt(request, builder)

            b['builds'] = []
            for build in builds:
                b['builds'].append(self.build_cxt(request, build))

            cxt['builders'].append(b)

        self.clearRecentBuildsCache()
        template = request.site.buildbot_service.templates.get_template("grid.html")
        defer.returnValue(template.render(**cxt))


class TransposedGridStatusResource(HtmlResource, GridStatusMixin):
    # TODO: docs
    status = None
    changemaster = None
    default_rev_order = "asc"

    @defer.inlineCallbacks
    def content(self, request, cxt):
        """This method builds the transposed grid display.
        That is, build hosts across the top, build stamps down the left side
        """

        # get url parameters
        numBuilds = int(request.args.get("length", [5])[0])
        tags = request.args.get("tag", [])
        if not tags:
            tags = request.args.get("category", [])
        branch = request.args.get("branch", [ANYBRANCH])[0]
        if branch == 'trunk':
            branch = None

        rev_order = request.args.get("rev_order", [self.default_rev_order])[0]
        if rev_order not in ["asc", "desc"]:
            rev_order = self.default_rev_order

        cxt['refresh'] = self.get_reload_time(request)

        # and the data we want to render
        status = self.getStatus(request)
        stamps = self.getRecentSourcestamps(status, numBuilds, tags, branch)

        cxt.update({'tags': tags,
                    'branch': branch,
                    'ANYBRANCH': ANYBRANCH,
                    'stamps': [map(SourceStamp.asDict, sstamp) for sstamp in stamps],
                    })

        sortedBuilderNames = util.naturalSort(status.getBuilderNames())

        cxt['sorted_builder_names'] = sortedBuilderNames
        cxt['builder_builds'] = builder_builds = []
        cxt['builders'] = builders = []
        cxt['range'] = range(len(stamps))
        if rev_order == "desc":
            cxt['range'].reverse()

        for bn in sortedBuilderNames:
            builds = [None] * len(stamps)

            builder = status.getBuilder(bn)
            if tags and not builder.matchesAnyTag(tags):
                continue

            for build in self.getRecentBuilds(builder, numBuilds, branch):
                # TODO: support multiple sourcestamps
                ss = build.getSourceStamps(absolute=True)
                key = self.getSourceStampKey(ss)

                for i, sstamp in enumerate(stamps):
                    if key == self.getSourceStampKey(sstamp) and builds[i] is None:
                        builds[i] = build

            b = yield self.builder_cxt(request, builder)
            builders.append(b)

            builder_builds.append(map(lambda b: self.build_cxt(request, b), builds))

        self.clearRecentBuildsCache()
        template = request.site.buildbot_service.templates.get_template('grid_transposed.html')
        defer.returnValue(template.render(**cxt))

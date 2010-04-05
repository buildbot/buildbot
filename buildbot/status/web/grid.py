from __future__ import generators

from buildbot.status.web.base import HtmlResource
from buildbot.status.web.base import build_get_class, path_to_builder, path_to_build
from buildbot.sourcestamp import SourceStamp

class ANYBRANCH: pass # a flag value, used below

class GridStatusMixin(object):
    def getTitle(self, request):
        status = self.getStatus(request)
        p = status.getProjectName()
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
            if not text: text = [ "(no information)" ]
            if text == [ "build", "successful" ]: text = [ "OK" ]
        else:
            text = [ 'building' ]

        name = build.getBuilder().getName()

        cxt = {}
        cxt['name'] = name
        cxt['url'] = path_to_build(request, build)
        cxt['text'] = text
        cxt['class'] = build_get_class(build)
        return cxt

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

        # TODO: for now, this pending/upcoming stuff is in the "current
        # activity" box, but really it should go into a "next activity" row
        # instead. The only times it should show up in "current activity" is
        # when the builder is otherwise idle.

        cxt = { 'url': path_to_builder(request, builder),
                'name': builder.getName(),
                'state': state,
                'n_pending': len(builder.getPendingBuilds()) }

        return cxt

    def getSourceStampKey(self, ss):
        """Given two source stamps, we want to assign them to the same row if
        they are the same version of code, even if they differ in minor detail.

        This function returns an appropriate comparison key for that.
        """
        return (ss.branch, ss.revision, ss.patch)

    def getRecentSourcestamps(self, status, numBuilds, categories, branch):
        """
        get a list of the most recent NUMBUILDS SourceStamp tuples, sorted
        by the earliest start we've seen for them
        """
        # TODO: use baseweb's getLastNBuilds?
        sourcestamps = { } # { ss-tuple : earliest time }
        for bn in status.getBuilderNames():
            builder = status.getBuilder(bn)
            if categories and builder.category not in categories:
                continue
            build = builder.getBuild(-1)
            while build:
                ss = build.getSourceStamp(absolute=True)
                start = build.getTimes()[0]
                build = build.getPreviousBuild()

                # skip un-started builds
                if not start: continue

                # skip non-matching branches
                if branch != ANYBRANCH and ss.branch != branch: continue

                key= self.getSourceStampKey(ss)
                if key not in sourcestamps or sourcestamps[key][1] > start:
                    sourcestamps[key] = (ss, start)

        # now sort those and take the NUMBUILDS most recent
        sourcestamps = sourcestamps.values()
        sourcestamps.sort(lambda x, y: cmp(x[1], y[1]))
        sourcestamps = map(lambda tup : tup[0], sourcestamps)
        sourcestamps = sourcestamps[-numBuilds:]

        return sourcestamps

class GridStatusResource(HtmlResource, GridStatusMixin):
    # TODO: docs
    status = None
    changemaster = None

    def content(self, request, cxt):
        """This method builds the regular grid display.
        That is, build stamps across the top, build hosts down the left side
        """

        # get url parameters
        numBuilds = int(request.args.get("width", [5])[0])
        categories = request.args.get("category", [])
        branch = request.args.get("branch", [ANYBRANCH])[0]
        if branch == 'trunk': branch = None

        # and the data we want to render
        status = self.getStatus(request)
        stamps = self.getRecentSourcestamps(status, numBuilds, categories, branch)

        cxt['refresh'] = self.get_reload_time(request)

        cxt.update({'categories': categories,
                    'branch': branch,
                    'ANYBRANCH': ANYBRANCH,
                    'stamps': map(SourceStamp.asDict, stamps)
                   })
        
        sortedBuilderNames = status.getBuilderNames()[:]
        sortedBuilderNames.sort()
        
        cxt['builders'] = []

        for bn in sortedBuilderNames:
            builds = [None] * len(stamps)

            builder = status.getBuilder(bn)
            if categories and builder.category not in categories:
                continue

            build = builder.getBuild(-1)
            while build and None in builds:
                ss = build.getSourceStamp(absolute=True)
                key= self.getSourceStampKey(ss)
                for i in range(len(stamps)):
                    if key == self.getSourceStampKey(stamps[i]) and builds[i] is None:
                        builds[i] = build
                build = build.getPreviousBuild()

            b = self.builder_cxt(request, builder)
            b['builds'] = []
            for build in builds:
                b['builds'].append(self.build_cxt(request, build))
            cxt['builders'].append(b)

        template = request.site.buildbot_service.templates.get_template("grid.html")
        return template.render(**cxt)


class TransposedGridStatusResource(HtmlResource, GridStatusMixin):
    # TODO: docs
    status = None
    changemaster = None

    def content(self, request, cxt):
        """This method builds the transposed grid display.
        That is, build hosts across the top, build stamps down the left side
        """

        # get url parameters
        numBuilds = int(request.args.get("length", [5])[0])
        categories = request.args.get("category", [])
        branch = request.args.get("branch", [ANYBRANCH])[0]
        if branch == 'trunk': branch = None

        cxt['refresh'] = self.get_reload_time(request)

        # and the data we want to render
        status = self.getStatus(request)
        stamps = self.getRecentSourcestamps(status, numBuilds, categories, branch)

        cxt.update({'categories': categories,
                    'branch': branch,
                    'ANYBRANCH': ANYBRANCH,
                    'stamps': map(SourceStamp.asDict, stamps),
                    })

        sortedBuilderNames = status.getBuilderNames()[:]
        sortedBuilderNames.sort()
        
        cxt['sorted_builder_names'] = sortedBuilderNames
        cxt['builder_builds'] = builder_builds = []
        cxt['builders'] = builders = []
        cxt['range'] = range(len(stamps))
        
        for bn in sortedBuilderNames:
            builds = [None] * len(stamps)

            builder = status.getBuilder(bn)
            if categories and builder.category not in categories:
                continue

            build = builder.getBuild(-1)
            while build and None in builds:
                ss = build.getSourceStamp(absolute=True)
                key = self.getSourceStampKey(ss)
                for i in range(len(stamps)):
                    if key == self.getSourceStampKey(stamps[i]) and builds[i] is None:
                        builds[i] = build
                build = build.getPreviousBuild()

            builders.append(self.builder_cxt(request, builder))
            builder_builds.append(map(lambda b: self.build_cxt(request, b), builds))

        template = request.site.buildbot_service.templates.get_template('grid_transposed.html')
        data = template.render(**cxt)
        return data


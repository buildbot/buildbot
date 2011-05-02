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


from buildbot.status.web.base import HtmlResource, BuildLineMixin, map_branches

# /one_line_per_build
#  accepts builder=, branch=, numbuilds=, reload=
class OneLinePerBuild(HtmlResource, BuildLineMixin):
    """This shows one line per build, combining all builders together. Useful
    query arguments:

    numbuilds=: how many lines to display
    builder=: show only builds for this builder. Multiple builder= arguments
              can be used to see builds from any builder in the set.
    reload=: reload the page after this many seconds
    """

    pageTitle = "Recent Builds"

    def __init__(self, numbuilds=20):
        HtmlResource.__init__(self)
        self.numbuilds = numbuilds

    def getChild(self, path, req):
        status = self.getStatus(req)
        builder = status.getBuilder(path)
        return OneLinePerBuildOneBuilder(builder, numbuilds=self.numbuilds)

    def get_reload_time(self, request):
        if "reload" in request.args:
            try:
                reload_time = int(request.args["reload"][0])
                return max(reload_time, 15)
            except ValueError:
                pass
        return None

    def content(self, req, cxt):
        status = self.getStatus(req)
        numbuilds = int(req.args.get("numbuilds", [self.numbuilds])[0])
        builders = req.args.get("builder", [])
        branches = [b for b in req.args.get("branch", []) if b]

        g = status.generateFinishedBuilds(builders, map_branches(branches),
                                          numbuilds, max_search=numbuilds)

        cxt['refresh'] = self.get_reload_time(req)
        cxt['num_builds'] = numbuilds
        cxt['branches'] =  branches
        cxt['builders'] = builders

        builds = cxt['builds'] = []
        for build in g:
            builds.append(self.get_line_values(req, build))

        cxt['authz'] = self.getAuthz(req)

        # get information on the builders - mostly just a count
        building = 0
        online = 0
        for bn in builders:
            builder = status.getBuilder(bn)
            builder_status = builder.getState()[0]
            if builder_status == "building":
                building += 1
                online += 1
            elif builder_status != "offline":
                online += 1

        cxt['num_online'] = online
        cxt['num_building'] = building

        template = req.site.buildbot_service.templates.get_template('onelineperbuild.html')
        return template.render(**cxt)



# /one_line_per_build/$BUILDERNAME
#  accepts branch=, numbuilds=

class OneLinePerBuildOneBuilder(HtmlResource, BuildLineMixin):
    def __init__(self, builder, numbuilds=20):
        HtmlResource.__init__(self)
        self.builder = builder
        self.builder_name = builder.getName()
        self.numbuilds = numbuilds
        self.pageTitle = "Recent Builds of %s" % self.builder_name

    def content(self, req, cxt):
        numbuilds = int(req.args.get("numbuilds", [self.numbuilds])[0])
        branches = [b for b in req.args.get("branch", []) if b]

        # walk backwards through all builds of a single builder
        g = self.builder.generateFinishedBuilds(map_branches(branches),
                                                numbuilds)

        cxt['builds'] = map(lambda b: self.get_line_values(req, b), g)
        cxt.update(dict(num_builds=numbuilds,
                        builder_name=self.builder_name,
                        branches=branches))    

        template = req.site.buildbot_service.templates.get_template('onelineperbuildonebuilder.html')
        return template.render(**cxt)



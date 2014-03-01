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

from buildbot.status.web.base import HtmlResource
from buildbot.status.web.base import IBox


class BuildStatusStatusResource(HtmlResource):

    def __init__(self, categories=None):
        HtmlResource.__init__(self)

    def content(self, request, ctx):
        """Display a build in the same format as the waterfall page.
        The HTTP GET parameters are the builder name and the build
        number."""

        status = self.getStatus(request)
        request.setHeader('Cache-Control', 'no-cache')

        # Get the parameters.
        name = request.args.get("builder", [None])[0]
        number = request.args.get("number", [None])[0]
        if not name or not number:
            return "builder and number parameter missing"
        number = int(number)

        # Check if the builder in parameter exists.
        try:
            builder = status.getBuilder(name)
        except:
            return "unknown builder"

        # Check if the build in parameter exists.
        build = builder.getBuild(int(number))
        if not build:
            return "unknown build %s" % number

        rows = ctx['rows'] = []

        # Display each step, starting by the last one.
        for i in range(len(build.getSteps()) - 1, -1, -1):
            step = build.getSteps()[i]
            if step.isStarted() and step.getText():
                rows.append(IBox(step).getBox(request).td(align="center"))

        # Display the bottom box with the build number in it.
        ctx['build'] = IBox(build).getBox(request).td(align="center")

        template = request.site.buildbot_service.templates.get_template("buildstatus.html")
        data = template.render(**ctx)

        # We want all links to display in a new tab/window instead of in the
        # current one.
        # TODO: Move to template
        data = data.replace('<a ', '<a target="_blank" ')
        return data

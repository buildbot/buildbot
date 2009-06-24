from buildbot.status.web.base import Box
from buildbot.status.web.base import HtmlResource
from buildbot.status.web.base import IBox

class BuildStatusStatusResource(HtmlResource):
    def __init__(self, categories=None):
        HtmlResource.__init__(self)

    def head(self, request):
        return ""

    def body(self, request):
        """Display a build in the same format as the waterfall page.
        The HTTP GET parameters are the builder name and the build
        number."""

        status = self.getStatus(request)
        data = ""

        # Get the parameters.
        name = request.args.get("builder", [None])[0]
        number = request.args.get("number", [None])[0]
        if not name or not number:
            return "builder and number parameter missing"

        # Main table for the build status.
        data += '<table>\n'

        # Check if the builder in parameter exists.
        try:
          builder = status.getBuilder(name)
        except:
            return "unknown builder"

        # Check if the build in parameter exists.
        build = builder.getBuild(int(number))
        if not build:
            return "unknown build %s" % number

        # Display each step, starting by the last one.
        for i in range(len(build.getSteps()) - 1, -1, -1):
            if build.getSteps()[i].getText():
                data += " <tr>\n"
                data += IBox(build.getSteps()[i]).getBox(request).td(align="center")
                data += " </tr>\n"

        # Display the bottom box with the build number in it.
        data += "<tr>"
        data += IBox(build).getBox(request).td(align="center")
        data += "</tr></table>\n"

        # We want all links to display in a new tab/window instead of in the
        # current one.
        data = data.replace('<a ', '<a target="_blank"')
        return data


from buildbot.status.web.base import HtmlResource
import buildbot
import twisted
import jinja2
import time, sys

class RootPage(HtmlResource):
    title = "Buildbot"

    def content(self, request, cxt):
        template = request.site.buildbot_service.templates.get_template("root.html")
        return template.render(**cxt)
        
from buildbot.status.web.base import HtmlResource
from buildbot.status.web.builder import BuildersResource
from buildbot import util

class LoginKatanaResource(HtmlResource):
    pageTitle = "Katana - Login"

    def content(self, req, cxt):
        status = self.getStatus(req)

        template = req.site.buildbot_service.templates.get_template("login.html")
        template.autoescape = True
        return template.render(**cxt)
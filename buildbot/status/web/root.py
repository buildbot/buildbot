from buildbot.status.web.base import HtmlResource

class RootPage(HtmlResource):
    title = "Buildbot"

    def content(self, request, cxt):
        template = request.site.buildbot_service.templates.get_template("root.html")
        return template.render(**cxt)
        
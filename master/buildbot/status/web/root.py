from twisted.web.util import redirectTo

from buildbot.status.web.base import HtmlResource, path_to_authfail
from buildbot.util.eventual import eventually

class RootPage(HtmlResource):
    title = "Buildbot"

    def content(self, request, cxt):
        status = self.getStatus(request)

        if request.path == '/shutdown':
            if self.getAuthz(request).actionAllowed("cleanShutdown", request):
                eventually(status.cleanShutdown)
                return redirectTo("/", request)
            else:
                return redirectTo(path_to_authfail(request), request)
        elif request.path == '/cancel_shutdown':
            if self.getAuthz(request).actionAllowed("cleanShutdown", request):
                eventually(status.cancelCleanShutdown)
                return redirectTo("/", request)
            else:
                return redirectTo(path_to_authfail(request), request)

        cxt.update(
                shutting_down = status.shuttingDown,
                shutdown_url = request.childLink("shutdown"),
                cancel_shutdown_url = request.childLink("cancel_shutdown"),
                )
        template = request.site.buildbot_service.templates.get_template("root.html")
        return template.render(**cxt)

from buildbot.status.web.auth import LogoutResource
from buildbot.status.web.base import HtmlResource, ActionResource, \
    path_to_login, path_to_authenticate
import urllib
from twisted.internet import defer
from twisted.web import server
from twisted.python import log


class LoginKatanaResource(HtmlResource):
    pageTitle = "Katana - Login"

    def content(self, req, cxt):
        status = self.getStatus(req)

        template = req.site.buildbot_service.templates.get_template("login.html")
        template.autoescape = True
        root = status.getBuildbotURL()
        cxt['authenticate_url'] = path_to_authenticate(req, root)
        return template.render(**cxt)

    def getChild(self, path, req):
        if path == "authenticate":
            return AuthenticateActionResource()
        if path == "api":
            return AuthenticateApiActionResource()

class  AuthenticateApiActionResource(ActionResource):

    @defer.inlineCallbacks
    def performAction(self, request):
        token = yield self.getAuthz(request).login(request)
        defer.returnValue(token)

    def render(self, request):
        d = defer.maybeDeferred(lambda : self.performAction(request))
        def redirect(token):
            response = '{%s}' % token if token else "{}"
            request.setHeader("content-type", "application/json")
            request.write(response)
            try:
                request.finish()
            except RuntimeError:
                log.msg("http client disconnected before results were sent")
        d.addCallback(redirect)

        def fail(f):
            request.processingFailed(f)
            return None
        d.addErrback(fail)
        return server.NOT_DONE_YET

class AuthenticateActionResource(ActionResource):

    def authorized(self, username):
        return "?authorized=True&user=%s" % username

    def performAction(self, request):
        authz = self.getAuthz(request)
        d = authz.login(request)
        status = request.site.buildbot_service.master.status
        root = status.getBuildbotURL()
        def on_login(token):
            if token:
                url = request.args.get('referer', None)
                if url is None or "authfail" in url[0]:
                    url = root
                else:
                    url = urllib.unquote(url[0])
                return url
            else:
                referer = urllib.unquote(request.args.get("referer", [root])[0])
                return path_to_login(request, referer, True)
        d.addBoth(on_login)
        return d

class LogoutKatanaResource(LogoutResource):

    def performAction(self, request):
        self.getAuthz(request).logoutUser(request)
        return LogoutResource.performAction(self, request)

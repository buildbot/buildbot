from twisted.internet import defer
from buildbot.status.web.auth import LogoutResource
from buildbot.status.web.authz import COOKIE_KEY
from buildbot.status.web.base import HtmlResource, ActionResource, \
    path_to_login, path_to_authenticate, path_to_root, path_to_authfail
import urllib
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

class AuthenticateActionResource(ActionResource):

    def authorized(self, username):
        return "?authorized=True&user=%s" % username

    def performAction(self, request):
       authz = self.getAuthz(request)
       d = authz.login(request)
       status = request.site.buildbot_service.master.status
       root = status.getBuildbotURL()

       def on_login(res):
           if res:

               url = request.args.get('referer', None)

               if "authfail" in url[0] or url is None:
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
        authz = self.getAuthz(request)
        s = authz.session(request)
        if s is not None:
            s.expire()
            request.addCookie(COOKIE_KEY, None, expires=s.getExpiration(), path="/")
        return LogoutResource.performAction(self, request)
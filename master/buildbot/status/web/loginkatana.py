from buildbot.status.web.base import HtmlResource, ActionResource, \
    path_to_login, path_to_authenticate
import ldap
import urllib

NOT_AUTORIZED = "?autorized=False"


class LoginKatanaResource(HtmlResource):
    pageTitle = "Katana - Login"

    def content(self, req, cxt):
        status = self.getStatus(req)

        template = req.site.buildbot_service.templates.get_template("login.html")
        template.autoescape = True
        cxt['authenticate_url'] = path_to_authenticate(req)
        return template.render(**cxt)

    def getChild(self, path, req):
        if path == "authenticate":
            return AuthenticateActionResource()

class AuthenticateActionResource(ActionResource):

    def __init__(self):
        ldap.set_option(ldap.OPT_TIMEOUT, 5.0)
        ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, 5.0)
        ldap.set_option(ldap.OPT_REFERRALS, 0)

    def authorized(self, username):
        return "?autorized=True&user=%s" % username

    def performAction(self, req):
        username = req.args.get("username", [None])[0]
        password = req.args.get("password", [None])[0]

        master = req.site.buildbot_service.master
        ldap_config = master.config.ldap
        l = ldap.initialize(ldap_config['ldap_server'])
        try:
            token = l.simple_bind_s("uid=%s,cn=users,%s" % (username, ldap_config['ldap_base_dn']), password)
            dn = l.whoami_s()
            attrs = ["cn"]
            filter_str = "uid=%s" % username
            ldap_result = l.search_s(ldap_config['ldap_base_dn'], ldap.SCOPE_SUBTREE, filterstr=filter_str, attrlist=attrs)
            fullname = username
            if ldap_result > 0 and ldap_result[0] > 1 and 'cn' in ldap_result[0][1].keys():
                fullname = ldap_result[0][1]['cn'][0]
            l.unbind()
            if dn:
                print 'ok', dn
        except Exception, e:
            return path_to_login(req) + NOT_AUTORIZED

        return path_to_login(req) + self.authorized(urllib.quote(fullname))
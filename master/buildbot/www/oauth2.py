import sanction

from buildbot.www import auth, resource
from twisted.internet import defer
from twisted.internet import threads
from posixpath import join


class OAuth2LoginResource(auth.LoginResource):
    # a LoginResource, which is already authenticated via a HTTPAuthSessionWrapper
    # disable reconfigResource calls
    needsReconfig = False

    def __init__(self, master, _auth):
        auth.LoginResource.__init__(self, master)
        self.auth = _auth

    @defer.inlineCallbacks
    def renderLogin(self, request):
        code = request.args.get("code", [""])[0]
        if not code:
            url = yield self.auth.getLoginURL()
            defer.returnValue(url)
        else:
            details = yield self.auth.verifyCode(code)
            request.getSession().user_infos = details
            raise resource.Redirect(self.auth.homeUri)


class OAuth2Auth(auth.AuthBase):
    name = 'oauth2'

    def __init__(self, authUri, tokenUri, clientId,
                 authUriConfig, tokenConfig):

        # userInfos are populated by the auth plugin directly
        auth.AuthBase.__init__(self, userInfos=None)
        self.authUri = authUri
        self.tokenUri = tokenUri
        self.clientId = clientId
        self.authUriConfig = authUriConfig
        self.tokenConfig = tokenConfig

    def reconfigAuth(self, master, new_config):
        self.master = master
        self.loginUri = join(new_config.www['url'], "login")
        self.homeUri = new_config.www['url']

    def getConfig(self, request):
        return dict(name=self.name,
                    oauth2=True,
                    fa_icon=self.faIcon
                    )
        pass

    def getSanction(self):
        # test hook point
        return sanction

    def getLoginResource(self, master):
        return OAuth2LoginResource(master, self)

    def getLoginURL(self):
        def thd():
            c = sanction.Client(auth_endpoint=self.authUri,
                                client_id=self.clientId)
            return c.auth_uri(redirect_uri=self.loginUri,
                              **self.authUriConfig)
        return threads.deferToThread(thd)

    def verifyCode(self, code):
        def thd():
            c = sanction.Client(token_endpoint=self.tokenUri,
                                client_id=self.clientId,
                                **self.tokenConfig)
            c.request_token(code=code,
                            redirect_uri=self.loginUri)

            return self.getUserInfosFromOAuthClient(c)
        return threads.deferToThread(thd)

    def getUserInfosFromOAuthClient(self, c):
        return {}


class GoogleAuth(OAuth2Auth):
    name = "Google"
    faIcon = "fa-google-plus"

    def __init__(self, clientId, clientSecret):
        OAuth2Auth.__init__(self,
                            authUri='https://accounts.google.com/o/oauth2/auth',
                            tokenUri='https://accounts.google.com/o/oauth2/token',
                            clientId=clientId,
                            authUriConfig=dict(scope=" ".join([
                                               'https://www.googleapis.com/auth/userinfo.email',
                                               'https://www.googleapis.com/auth/userinfo.profile',
                                               ]),
                                               access_type='offline'),
                            tokenConfig=dict(
                                resource_endpoint='https://www.googleapis.com/oauth2/v1',
                                client_secret=clientSecret,
                                token_transport=sanction.transport_headers)
                            )

    def getUserInfosFromOAuthClient(self, c):
        data = c.request('/userinfo')
        return dict(full_name=data["name"],
                    email=data["email"],
                    avatar_url=data["picture"])


class GithubAuth(OAuth2Auth):
    name = "Github"
    faIcon = "fa-github"

    def __init__(self, clientId, clientSecret):
        OAuth2Auth.__init__(self,
                            authUri='https://github.com/login/oauth/authorize',
                            tokenUri='https://github.com/login/oauth/access_token',
                            clientId=clientId,
                            authUriConfig=dict(),
                            tokenConfig=dict(
                                resource_endpoint='https://api.github.com',
                                client_secret=clientSecret,
                                token_transport=sanction.transport_headers)
                            )

    def getUserInfosFromOAuthClient(self, c):
        user = c.request('/user')
        orgs = c.request(join('/users', user['login'], "orgs"))
        return dict(full_name=user['name'],
                    email=user['email'],
                    username=user['login'],
                    groups=[org['login'] for org in orgs])

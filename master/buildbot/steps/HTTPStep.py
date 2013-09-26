# use the 'requests' lib: http://python-requests.org

from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import SUCCESS, FAILURE
from buildbot import config
from twisted.internet import defer

try:
    import txrequests
    import requests
except ImportError:
    config.error("Please install txrequests to use this step (pip install txrequests)")

_session = None
def getSession():
    global _session
    if _session is None:
        _session = txrequests.Session()
    return _session

def setSession(session):
    global _session
    _session = session

def closeSession():
    global _session
    if _session is not None:
        _session.close()

class HTTPStep(BuildStep):

    name = 'HTTPStep'
    description = 'Requesting'
    descriptionDone = 'Requested'
    requestsParams = [ "method", "url", "params", "data", "headers",
                        "cookies", "files", "auth",
                        "timeout", "allow_redirects", "proxies",
                        "hooks", "stream", "verify", "cert" ]
    renderables = requestsParams

    def __init__(self, url, method, description=None, descriptionDone=None, **kwargs):
        BuildStep.__init__(self, **kwargs)
        self.session = getSession()
        self.requestkwargs = {'method': method, 'url': url}
        for p in HTTPStep.requestsParams:
            v = kwargs.pop(p, None)
            if v is not None:
                self.requestkwargs[p] = v

        if method not in ('POST', 'GET', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'):
            config.error("Wrong method given: '%s' is not known" % method)
        if description is not None:
            self.description = description
        if descriptionDone is not None:
            self.descriptionDone = descriptionDone

    def start(self):
        self.doRequest()

    @defer.inlineCallbacks
    def doRequest(self):
        log = self.addLog('log')
        # known methods already tested in __init__

        log.addHeader('Performing %s request to %s\n' % (self.method, self.url))
        if self.params:
            log.addHeader('Parameters:\n')
            for k, v in self.requestkwargs.get("params", {}).iteritems():
                log.addHeader('\t%s: %s\n' % (k, v))
        data = self.requestkwargs.get("data", None)
        if data:
            log.addHeader('Data:\n')
            if type(data) == dict:
                for k, v in data.iteritems():
                    log.addHeader('\t%s: %s\n' % (k, v))
            else:
                log.addHeader('\t%s\n' % data)


        try:
            r = yield self.session.request(**self.requestkwargs)
        except requests.exceptions.ConnectionError, e:
            log.addStderr('An exception occured while performing the request: %s' % e)
            self.finished(FAILURE)
            return

        if r.history:
            log.addStdout('\nRedirected %d times:\n\n' % len(r.history))
            for rr in r.history:
                self.log_request(rr)
                log.addStdout('=' * 60 + '\n')

        self.log_request(r)

        log.finish()

        self.step_status.setText(self.describe(done=True))
        if (r.status_code < 400):
            self.finished(SUCCESS)
        else:
            self.finished(FAILURE)

    def log_request(self, request):
        log = self.getLog('log')

        log.addHeader('Request Header:\n')
        for k, v in request.request.headers.iteritems():
            log.addHeader('\t%s: %s\n' % (k, v))

        log.addStdout('URL: %s\n' % request.url)

        if request.status_code == requests.codes.ok:
            log.addStdout('Status: %s\n' % request.status_code)
        else:
            log.addStderr('Status: %s\n' % request.status_code)

        log.addHeader('Response Header:\n')
        for k, v in request.headers.iteritems():
            log.addHeader('\t%s: %s\n' % (k, v))

        log.addStdout(' ------ Content ------\n%s' % request.text)

    def describe(self, done=False):
        if done:
            return self.descriptionDone.split()
        return self.description.split()

class POST(HTTPStep):
    def __init__(self, url, **kwargs):
        HTTPStep.__init__(self, url, method='POST', **kwargs)

class GET(HTTPStep):
    def __init__(self, url, **kwargs):
        HTTPStep.__init__(self, url, method='GET', **kwargs)

class PUT(HTTPStep):
    def __init__(self, url, **kwargs):
        HTTPStep.__init__(self, url, method='PUT', **kwargs)

class DELETE(HTTPStep):
    def __init__(self, url, **kwargs):
        HTTPStep.__init__(self, url, method='DELETE', **kwargs)

class HEAD(HTTPStep):
    def __init__(self, url, **kwargs):
        HTTPStep.__init__(self, url, method='HEAD', **kwargs)

class OPTIONS(HTTPStep):
    def __init__(self, url, **kwargs):
        HTTPStep.__init__(self, url, method='OPTIONS', **kwargs)

